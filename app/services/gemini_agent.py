import json
from google import genai
from google.genai import types
from app.core.config import settings
from app.models.booking import BookingCreateRequest, BookingResponse, ChatResponse, ADULT_PRICE, CHILD_PRICE
from app.services.booking_service import AvailabilityEngine

SYSTEM_INSTRUCTION = """
You are "Reservas Iturrieta" â€” the warm, knowledgeable hospitality concierge for Sidreria Iturrieta
(Aramaio, Alava. Est. 1998). Your mission: welcome guests, share our authentic Basque cider tradition,
and manage table reservations through a friendly, step-by-step conversation.

Atmosphere & Heritage:
- Location: Arraga auzoa, 2, 01169 Aramaio, Alava.
- Menu: Traditional Basque Cider House menu â€” Txuleta ribeye steak over charcoal, codfish omelette,
  Idiazabal cheese with walnuts, unlimited natural cider straight from the barrel (txotx).
- Hours: Friday, Saturday, and Sunday lunch only (13:00 to 16:00).
- Dinner & Weekdays (Mon-Thu): Closed to the public.

Pricing:
- Adults: 45 EUR per person (includes full menu + unlimited cider).
- Children (under 12): 22 EUR per person (half menu, soft drinks included).

Booking Flow (follow this order STRICTLY):
1. Collect: Guest Name, Phone (with country code), Preferred Date, Preferred Time (13:00-15:30),
   Number of ADULTS, Number of CHILDREN under 12.
   - party_size = adults + children.
   - If the user does not mention children, ask once politely. If they say none, set children=0.
2. Before calling book_table_tool, show a clear booking summary and ask the user to confirm.
   Example: "Just to confirm â€” shall I go ahead and secure this table for you?"
3. Only call book_table_tool AFTER the user says yes / ok / sure / confirm / go ahead, etc.
4. After book_table_tool returns status "confirmed", reply with this format:

Reservation Confirmed! âœ…

Name: [guest_name]
Date: [friendly date, e.g. Friday, 31 October 2026]
Time: [time]
Table: [table_name] Â· [section]
Guests: [adults] Adult(s) + [children] Child(ren) = [party_size] total
Total Estimated Amount: EUR [total_price]
  (Adults: [adults] x EUR 45 | Children: [children] x EUR 22)

Thank you, [first_name]! We look forward to welcoming you to Sidreria Iturrieta.
Come ready to enjoy our txotx cider experience! ðŸŽ

If you need to make any changes, just send us a message.

5. If book_table_tool returns status "declined", apologise and explain the reason clearly.
6. If book_table_tool returns status "requested", explain we will confirm within 24 hours.

Keep responses warm, brief, and in the same language the guest uses.
Never expose internal tool names or technical errors to the user.
"""

def get_gemini_client():
    if not settings.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=settings.GEMINI_API_KEY)

# Global store for tool execution result in the current turn
_current_turn_booking: dict = {}

def book_table_tool(
    guest_name: str,
    phone: str,
    party_size: int,
    adults: int,
    children: int,
    service_date: str,
    service_time: str,
    note: str = "",
) -> str:
    """Checks real-time table availability and confirms reservation immediately.
    Call this ONLY after the guest has confirmed their booking details."""
    req = BookingCreateRequest(
        guest_name=guest_name,
        phone=phone,
        party_size=party_size,
        adults=adults,
        children=children,
        service_date=service_date,
        service_time=service_time,
        channel="web",
        note=note,
    )
    res = AvailabilityEngine.process_booking(req)
    _current_turn_booking["latest"] = res
    return json.dumps({
        "status": res.status,
        "table": res.table.table_name if res.table else None,
        "section": res.table.section if res.table else None,
        "adults": res.adults,
        "children": res.children,
        "total_price": res.total_price,
        "message": res.confirmation_message,
    })

class GeminiAgentService:
    @classmethod
    async def chat(cls, user_message: str, history: list = None, channel: str = "web") -> ChatResponse:
        client = get_gemini_client()
        
        if not client:
            return ChatResponse(
                reply="Welcome to Reservas Iturrieta. Please configure GEMINI_API_KEY in the backend .env file to activate our assistant. In the meantime, feel free to use the online booking form!"
            )

        _current_turn_booking.clear()

        # Format past conversation history
        formatted_history = []
        for h in (history or []):
            role = "user" if h.role == "user" else "model"
            formatted_history.append(types.Content(role=role, parts=[types.Part.from_text(text=h.content)]))

        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
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
                friendly = "Our AI servers are experiencing high demand at this moment. You can still reserve your table directly using the booking form right on this page, or try asking again in a minute!"
            else:
                friendly = "I am currently unable to process your request. Please feel free to use our online booking form or message our Telegram bot @IturrietaBookingBot directly."
            return ChatResponse(reply=friendly)

        booking_obj = _current_turn_booking.get("latest")

        return ChatResponse(
            reply=response_text,
            booking_created=booking_obj
        )

