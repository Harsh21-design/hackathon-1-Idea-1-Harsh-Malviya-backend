import json
from google import genai
from google.genai import types
from app.core.config import settings
from app.models.booking import BookingCreateRequest, BookingResponse, ChatResponse
from app.services.booking_service import AvailabilityEngine

SYSTEM_INSTRUCTION = """
You are "Reservas Iturrieta" — the friendly, warm hospitality concierge for Sidrería Iturrieta (Aramaio, Álava · Est. 1998).
Your mission is to welcome guests, share our authentic Basque cider tradition, and instantly manage table reservations.

Atmosphere & Heritage:
- Location: Arraga auzoa, 2, 01169 Aramaio, Álava.
- Menu: Traditional Basque Cider House menu (Txuleta ribeye steak over charcoal, codfish omelette, Idiazabal cheese with walnuts, unlimited natural cider directly from the barrel / 'txotx').
- Hours: Friday, Saturday, and Sunday lunch only (13:00 to 16:00).
- Dinner & Weekdays (Mon-Thu): Closed to the public.

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

# Global store for tool execution result in the current turn
_current_turn_booking: dict = {}

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
    _current_turn_booking["latest"] = res
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

        _current_turn_booking.clear()

        # Format past conversation history
        formatted_history = []
        for h in (history or []):
            role = "user" if h.role == "user" else "model"
            formatted_history.append(types.Content(role=role, parts=[types.Part.from_text(text=h.content)]))

        models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
        response_text = ""
        last_err = None

        for model_candidate in models_to_try:
            try:
                # Use recommended chats.create API for clean Automatic Function Calling (AFC)
                chat_session = client.chats.create(
                    model=model_candidate,
                    history=formatted_history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=[book_table_tool],
                        temperature=0.7,
                    )
                )

                response = chat_session.send_message(user_message)
                if response and response.text:
                    response_text = response.text
                    break
            except Exception as model_err:
                last_err = model_err
                continue

        if not response_text:
            err_str = str(last_err or "")
            if "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str:
                friendly = "Kaixo! Our AI servers are experiencing high demand at this moment. You can still reserve your table directly using the booking form right on this page, or try asking again in a minute!"
            else:
                friendly = "Kaixo! I am currently unable to process your request. Please feel free to use our online booking form or message our Telegram bot @IturrietaBookingBot directly."
            return ChatResponse(reply=friendly)

        booking_obj = _current_turn_booking.get("latest")

        return ChatResponse(
            reply=response_text,
            booking_created=booking_obj
        )
