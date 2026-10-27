import json
from groq import Groq
from app.core.config import settings
from app.models.booking import BookingCreateRequest, BookingResponse, ChatResponse
from app.services.booking_service import AvailabilityEngine

SYSTEM_INSTRUCTION = """
You are "Reservas Iturrieta" — the ultra-fast, polite hospitality concierge for Sidrería Iturrieta (Aramaio, Álava · Est. 1998).
Your mission is to welcome guests, answer questions about our Basque cider house, and instantly confirm table reservations.

Atmosphere & Heritage:
- Location: Arraga auzoa, 2, 01169 Aramaio, Álava.
- Menu: Traditional Basque Cider House menu (Txuleta ribeye steak over charcoal, codfish omelette, Idiazabal cheese with walnuts, unlimited cider straight from the barrel / 'txotx'). Price: €45/guest. Children: €16.
- Hours: Friday, Saturday, and Sunday lunch only (13:00 to 16:00).
- Closed: Monday to Thursday and dinners.

Core Capability:
When a guest wants to book or check availability:
1. Confirm: Name, Contact Phone, Date (YYYY-MM-DD), Service Time (13:00 to 15:30), and Guest Count (1-35).
2. Call the ook_table_tool function to check live tables and confirm instantly.
3. Keep answers concise, warm, and helpful.
"""

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_table_tool",
            "description": "Checks real-time table availability and confirms reservation immediately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string", "description": "Full name of the contact person"},
                    "phone": {"type": "string", "description": "Phone number with country code"},
                    "party_size": {"type": "integer", "description": "Number of diners (1-35)"},
                    "service_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "service_time": {"type": "string", "description": "Time in HH:MM format (between 13:00 and 15:30)"},
                    "note": {"type": "string", "description": "Special dietary or seating notes"}
                },
                "required": ["guest_name", "phone", "party_size", "service_date", "service_time"]
            }
        }
    }
]

def execute_booking(args: dict, channel: str) -> BookingResponse:
    req = BookingCreateRequest(
        guest_name=args.get("guest_name", "Guest"),
        phone=args.get("phone", ""),
        party_size=int(args.get("party_size", 2)),
        service_date=args.get("service_date", ""),
        service_time=args.get("service_time", "13:30"),
        channel="telegram" if channel == "telegram" else "web",
        note=args.get("note", "Booked via Reservas Iturrieta AI")
    )
    return AvailabilityEngine.process_booking(req)

class GroqAgentService:
    @classmethod
    async def chat(cls, user_message: str, history: list = None, channel: str = "web") -> ChatResponse:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return ChatResponse(
                reply="Kaixo! Welcome to Reservas Iturrieta. Please add GROQ_API_KEY in the backend .env file to activate our ultra-fast Groq AI assistant."
            )

        try:
            client = Groq(api_key=api_key)

            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for h in (history or []):
                role = "assistant" if h.role == "model" else h.role
                messages.append({"role": role, "content": h.content})

            messages.append({"role": "user", "content": user_message})

            # Fast active Groq model
            model_to_use = "qwen/qwen3.8-27b"

            completion = client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                tools=GROQ_TOOLS,
                tool_choice="auto",
                temperature=0.6,
                max_tokens=600
            )

            msg = completion.choices[0].message
            created_booking = None

            # Check if Groq called the booking tool
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "book_table_tool":
                        args = json.loads(tool_call.function.arguments)
                        created_booking = execute_booking(args, channel)
                        
                        messages.append(msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "status": created_booking.status,
                                "table": created_booking.table.table_name if created_booking.table else None,
                                "message": created_booking.confirmation_message
                            })
                        })
                        follow_up = client.chat.completions.create(
                            model=model_to_use,
                            messages=messages,
                            temperature=0.6
                        )
                        return ChatResponse(
                            reply=follow_up.choices[0].message.content or created_booking.confirmation_message,
                            booking_created=created_booking
                        )

            return ChatResponse(
                reply=msg.content or "Kaixo! Welcome to Reservas Iturrieta. How can I assist you with your table reservation or visit today?",
                booking_created=None
            )

        except Exception as e:
            return ChatResponse(
                reply=f"Reservas Iturrieta temporary notice: {str(e)}"
            )
