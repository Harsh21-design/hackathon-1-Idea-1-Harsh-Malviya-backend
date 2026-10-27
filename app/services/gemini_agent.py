import json
from google import genai
from google.genai import types
from app.core.config import settings
from app.models.booking import BookingCreateRequest, BookingResponse, ChatResponse
from app.services.booking_service import AvailabilityEngine

SYSTEM_INSTRUCTION = """
You are "Reservas Iturrieta" — the intelligent hospitality reservation assistant for Sidrería Iturrieta (Aramaio, Álava · Est. 1998).
Your mission is to welcome guests, share our authentic Basque cider tradition, and instantly manage table reservations.

Atmosphere & Heritage:
- Arraga auzoa, 2, 01169 Aramaio, Álava.
- Menu: Traditional Basque Cider House menu (Txuleta ribeye steak over charcoal, codfish omelette, Idiazabal cheese with walnuts, unlimited cider directly from the barrel / 'txotx').
- Hours: Friday, Saturday, and Sunday lunch only (13:00 to 16:00).

Core Capability:
When a guest wants to book or check availability:
1. Confirm their Name, Contact Phone, Date (YYYY-MM-DD), Service Time (13:00 to 15:30), and Guest Count (1-35).
2. Execute the ook_table_tool function to check live table availability and secure instant confirmation.
3. Keep answers clear, polite, and welcoming.
"""

def get_gemini_client():
    if not settings.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=settings.GEMINI_API_KEY)

def book_table_tool(guest_name: str, phone: str, party_size: int, service_date: str, service_time: str, note: str = "") -> str:
    """Checks real-time table availability and confirms reservation immediately."""
    req = BookingCreateRequest(
        guest_name=guest_name,
        phone=phone,
        party_size=party_size,
        service_date=service_date,
        service_time=service_time,
        channel="web",
        note=note
    )
    res = AvailabilityEngine.process_booking(req)
    return json.dumps({
        "status": res.status,
        "table": res.table.table_name if res.table else None,
        "section": res.table.section if res.table else None,
        "message": res.confirmation_message
    })

class GeminiAgentService:
    @classmethod
    async def chat(cls, user_message: str, history: list = None, channel: str = "web") -> ChatResponse:
        client = get_gemini_client()
        
        if not client:
            return ChatResponse(
                reply="Kaixo! Welcome to Reservas Iturrieta. Please configure GEMINI_API_KEY in the backend .env file to activate our assistant. In the meantime, feel free to use the online booking form!"
            )

        try:
            contents = []
            for h in (history or []):
                role = "user" if h.role == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h.content)]))
            
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

            # Fallback list of models in case of 503 high demand spikes
            models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
            response = None
            last_err = None

            for model_candidate in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_candidate,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            tools=[book_table_tool],
                            temperature=0.7,
                        )
                    )
                    if response:
                        break
                except Exception as model_err:
                    last_err = model_err
                    continue

            if not response:
                raise last_err or Exception("All AI models currently busy.")

            created_booking = None
            reply_text = ""

            if response.function_calls:
                for call in response.function_calls:
                    if call.name == "book_table_tool":
                        args = call.args
                        req = BookingCreateRequest(
                            guest_name=args.get("guest_name", "Guest"),
                            phone=args.get("phone", ""),
                            party_size=int(args.get("party_size", 2)),
                            service_date=args.get("service_date", ""),
                            service_time=args.get("service_time", "13:30"),
                            channel="telegram" if channel == "telegram" else "web",
                            note=args.get("note", "Booked via Reservas Iturrieta")
                        )
                        created_booking = AvailabilityEngine.process_booking(req)
                        reply_text = created_booking.confirmation_message
            
            if not reply_text and response.text:
                reply_text = response.text

            return ChatResponse(
                reply=reply_text or "Kaixo! How can Reservas Iturrieta assist you today?",
                booking_created=created_booking
            )

        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str:
                friendly = "Kaixo! Our AI servers are experiencing high demand at this moment. You can still reserve your table directly using the booking form right on this page, or try asking again in a minute!"
            else:
                friendly = "Kaixo! I am currently unable to process your request. Please feel free to use our online booking form or message our Telegram bot @IturrietaBookingBot directly."
            return ChatResponse(reply=friendly)
