import json
import logging
from groq import Groq
from app.core.config import settings
from app.models.booking import BookingCreateRequest, BookingResponse, ChatResponse, ADULT_PRICE, CHILD_PRICE
from app.services.booking_service import AvailabilityEngine

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
You are "Reservas Iturrieta" -- the warm, knowledgeable hospitality concierge for Sidreria Iturrieta
(Aramaio, Alava. Est. 1998). Your mission: welcome guests, share our Basque cider tradition,
and manage table reservations through a friendly step-by-step conversation.

Restaurant Info:
- Location: Arraga auzoa, 2, 01169 Aramaio, Alava.
- Menu: Traditional Basque Cider House -- Txuleta ribeye steak over charcoal, codfish omelette,
  Idiazabal cheese with walnuts, unlimited natural cider from the barrel (txotx).
- Hours: Friday, Saturday, and Sunday lunch only (13:00 to 16:00). Closed Mon-Thu and evenings.

Pricing:
- Adults: 45 EUR per person (full menu + unlimited cider).
- Children (under 12): 22 EUR per person (half menu, soft drinks).

Booking Flow (STRICTLY in this order):
1. Collect all required details one by one in a friendly way:
   - Guest Name
   - Phone number (with country code)
   - Date (YYYY-MM-DD)
   - Time (13:00 to 15:30)
   - Number of ADULTS
   - Number of CHILDREN under 12 (ask once; if none, set to 0)
   - party_size = adults + children
2. Once all details collected, show a clear summary and ask user to confirm:
   Example: "Here is your booking summary: [details]. Shall I go ahead and secure your table?"
3. ONLY call book_table_tool AFTER user explicitly confirms (yes / ok / sure / go ahead / confirm).
4. After book_table_tool returns status "confirmed", respond with this exact format:

Reservation Confirmed! 

Name: [guest_name]
Date: [friendly date, e.g. Friday, 31 October 2026]
Time: [time]
Table: [table_name] - [section]
Guests: [adults] Adult(s) + [children] Child(ren) = [party_size] total
Total Estimated Amount: EUR [total_price]
  (Adults: [adults] x EUR 45 | Children: [children] x EUR 22)

Thank you, [first_name]! We look forward to welcoming you to Sidreria Iturrieta.
Come ready to enjoy our txotx cider experience!

If you need any changes, just message us.

5. If status is "declined", apologise and explain the reason clearly.
6. If status is "requested", say we will confirm within 24 hours.

Keep responses warm, friendly, and brief. Always communicate in plain English only. Do NOT use any Basque words or greetings (no "Kaixo", no "Kaxerrak", etc.). Start greetings with "Hello" or "Welcome".
Never show raw tool names, JSON, or technical errors to the user.
"""

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_table_tool",
            "description": "Checks real-time table availability and confirms reservation. Call ONLY after guest confirms the booking summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string", "description": "Full name of the contact person"},
                    "phone": {"type": "string", "description": "Phone number with country code"},
                    "party_size": {"type": "integer", "description": "Total diners = adults + children"},
                    "adults": {"type": "integer", "description": "Number of adults (45 EUR each)"},
                    "children": {"type": "integer", "description": "Number of children under 12 (22 EUR each)"},
                    "service_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "service_time": {"type": "string", "description": "Time in HH:MM format (13:00 to 15:30)"},
                    "note": {"type": "string", "description": "Special dietary or seating notes"}
                },
                "required": ["guest_name", "phone", "party_size", "adults", "children", "service_date", "service_time"]
            }
        }
    }
]


def execute_booking(args: dict, channel: str) -> BookingResponse:
    adults = int(args.get("adults", 0))
    children = int(args.get("children", 0))
    party_size = int(args.get("party_size", adults + children))
    if adults + children != party_size:
        adults = party_size - children

    req = BookingCreateRequest(
        guest_name=args.get("guest_name", "Guest"),
        phone=args.get("phone", ""),
        party_size=party_size,
        adults=adults,
        children=children,
        service_date=args.get("service_date", ""),
        service_time=args.get("service_time", "13:30"),
        channel="telegram" if channel == "telegram" else "web",
        note=args.get("note", "")
    )
    return AvailabilityEngine.process_booking(req)


class GroqAgentService:
    @classmethod
    async def chat(cls, user_message: str, history: list = None, channel: str = "web") -> ChatResponse:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return ChatResponse(
                reply="Welcome to Reservas Iturrieta. Please add GROQ_API_KEY in the backend .env file to activate the AI assistant."
            )

        try:
            client = Groq(api_key=api_key)

            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for h in (history or []):
                role = "assistant" if h.role == "model" else h.role
                messages.append({"role": role, "content": h.content})
            messages.append({"role": "user", "content": user_message})

            # Models active and supported on user's Groq tier
            models_to_try = [
                "qwen/qwen3.8-27b",
                "openai/gpt-oss-120b",
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
            ]

            completion = None
            last_err = None
            for model in models_to_try:
                try:
                    completion = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=GROQ_TOOLS,
                        tool_choice="auto",
                        temperature=0.6,
                        max_tokens=800,
                    )
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"Groq model {model} failed: {e}")
                    continue

            if completion is None:
                logger.error(f"All Groq models failed. Last error: {last_err}")
                return ChatResponse(
                    reply="Our AI is experiencing a temporary issue. Please try again in a moment or use our online booking form!"
                )

            msg = completion.choices[0].message
            created_booking = None

            # Handle tool call (booking)
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "book_table_tool":
                        args = json.loads(tool_call.function.arguments)
                        created_booking = execute_booking(args, channel)

                        tool_result = json.dumps({
                            "status": created_booking.status,
                            "table": created_booking.table.table_name if created_booking.table else None,
                            "section": created_booking.table.section if created_booking.table else None,
                            "adults": created_booking.adults,
                            "children": created_booking.children,
                            "total_price": created_booking.total_price,
                            "message": created_booking.confirmation_message,
                        })

                        messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        })

                        # Get final human-readable response from Groq
                        follow_up = None
                        for model in models_to_try:
                            try:
                                follow_up = client.chat.completions.create(
                                    model=model,
                                    messages=messages,
                                    temperature=0.6,
                                    max_tokens=600,
                                )
                                break
                            except Exception:
                                continue

                        final_reply = (
                            follow_up.choices[0].message.content
                            if follow_up and follow_up.choices[0].message.content
                            else created_booking.confirmation_message
                        )
                        return ChatResponse(reply=final_reply, booking_created=created_booking)

            return ChatResponse(
                reply=msg.content or "Welcome to Reservas Iturrieta. How can I help you today?",
                booking_created=None,
            )

        except Exception as e:
            logger.error(f"Groq chat exception: {e}")
            err = str(e)
            if "rate_limit" in err.lower() or "429" in err:
                return ChatResponse(reply="Our AI is a bit busy right now. Please try again in a moment!")
            return ChatResponse(reply="I could not process that request. Please use our online booking form or contact us via Telegram @IturrietaBookingBot.")

