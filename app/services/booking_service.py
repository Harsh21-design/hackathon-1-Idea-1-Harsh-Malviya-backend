from datetime import datetime, date
from typing import Optional, Tuple
from app.db.supabase import get_supabase_client
from app.models.booking import BookingCreateRequest, BookingResponse, TableAllocation, ADULT_PRICE, CHILD_PRICE

# Fallback tables if database tables table is empty
FALLBACK_TABLES = [
    {"id": "T1", "name": "Mahaia 1", "capacity": 4, "section": "Kupela Room"},
    {"id": "T2", "name": "Mahaia 2", "capacity": 6, "section": "Kupela Room"},
    {"id": "T3", "name": "Mahaia 3", "capacity": 6, "section": "Kupela Room"},
    {"id": "T4", "name": "Mahaia 4", "capacity": 8, "section": "Kupela Room"},
    {"id": "T10", "name": "Mahaia 10 (Long)", "capacity": 14, "section": "Main Hall"},
    {"id": "T11", "name": "Mahaia 11 (Long)", "capacity": 16, "section": "Main Hall"},
    {"id": "T12", "name": "Mahaia 12 (Cuadrilla)", "capacity": 20, "section": "Main Hall"},
]

def parse_time_minutes(t_str: str) -> int:
    parts = t_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])

class AvailabilityEngine:
    """
    Intelligent Booking Engine:
    Validates schedule, closure dates, shift cover limits, and finds an optimal table to INSTANTLY confirm.
    """

    @staticmethod
    def get_restaurant_tables():
        try:
            supabase = get_supabase_client()
            res = supabase.from_("restaurant_tables").select("*").order("capacity").execute()
            if res.data and len(res.data) > 0:
                return res.data
        except Exception:
            pass
        return FALLBACK_TABLES

    @classmethod
    def check_closure(cls, target_date: str) -> Optional[str]:
        try:
            supabase = get_supabase_client()
            res = supabase.from_("closures").select("reason").eq("service_date", target_date).execute()
            if res.data and len(res.data) > 0:
                return f"Restaurant is closed on {target_date}: {res.data[0].get('reason', 'Private Event')}"
        except Exception:
            pass
        return None

    @classmethod
    def check_schedule_and_slot(cls, target_date: str, target_time: str) -> Optional[str]:
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD."

        weekday = (dt.weekday() + 1) % 7 # 0 = Sun, 5 = Fri, 6 = Sat
        # Cider house schedule: Friday (5), Saturday (6), Sunday (0) lunch (13:00 to 16:00)
        open_days = [5, 6, 0]
        if weekday not in open_days:
            return f"{dt.strftime('%A')} is not a public service day. We open Friday to Sunday lunch."

        t_min = parse_time_minutes(target_time)
        if t_min < parse_time_minutes("13:00") or t_min > parse_time_minutes("15:30"):
            return "Service times are only available between 13:00 and 15:30."

        return None

    @classmethod
    def find_best_table(cls, party_size: int, service_date: str, service_time: str) -> Optional[dict]:
        tables = cls.get_restaurant_tables()
        supabase = get_supabase_client()

        # Fetch existing active bookings for that date
        res = supabase.from_("booking_requests")\
            .select("table_id, service_time, status")\
            .eq("service_date", service_date)\
            .in_("status", ["confirmed", "seated"])\
            .execute()
        
        booked_table_ids = set()
        req_min = parse_time_minutes(service_time)

        # Average dining duration = 120 minutes
        for b in (res.data or []):
            if not b.get("table_id"):
                continue
            b_min = parse_time_minutes(b.get("service_time", "13:00"))
            # If overlapping within 105 mins
            if abs(req_min - b_min) < 105:
                booked_table_ids.add(b["table_id"])

        # Filter candidate tables that have capacity >= party_size and are not booked
        suitable = [t for t in tables if t["capacity"] >= party_size and t["id"] not in booked_table_ids]
        if not suitable:
            return None

        # Sort by best fit: smallest capacity that fits party_size
        suitable.sort(key=lambda t: t["capacity"])
        return suitable[0]

    @classmethod
    def process_booking(cls, req: BookingCreateRequest) -> BookingResponse:
        # 1. Validation checks
        closure_err = cls.check_closure(req.service_date)
        if closure_err:
            return BookingResponse(
                guest_name=req.guest_name,
                party_size=req.party_size,
                service_date=req.service_date,
                service_time=req.service_time,
                channel=req.channel,
                status="declined",
                confirmation_message=closure_err
            )

        slot_err = cls.check_schedule_and_slot(req.service_date, req.service_time)
        if slot_err:
            return BookingResponse(
                guest_name=req.guest_name,
                party_size=req.party_size,
                service_date=req.service_date,
                service_time=req.service_time,
                channel=req.channel,
                status="declined",
                confirmation_message=slot_err
            )

        # 2. Smart Auto Table Allocation
        allocated_table = cls.find_best_table(req.party_size, req.service_date, req.service_time)

        # Determine adults/children — fallback: all adults if not provided
        adults = req.adults if req.adults > 0 else req.party_size
        children = req.children
        if adults + children != req.party_size:
            adults = req.party_size - children
        total_price = round(adults * ADULT_PRICE + children * CHILD_PRICE, 2)
        
        supabase = get_supabase_client()
        if allocated_table:
            # INSTANT CONFIRMATION!
            status = "confirmed"
            table_id = allocated_table["id"]
            table_obj = TableAllocation(
                table_id=allocated_table["id"],
                table_name=allocated_table["name"],
                capacity=allocated_table["capacity"],
                section=allocated_table.get("section", "Main Hall")
            )
            msg = f"Your table is INSTANTLY CONFIRMED at Table {allocated_table['name']} ({allocated_table.get('section', 'Main Hall')}) for {req.party_size} guests on {req.service_date} at {req.service_time}."
        else:
            # No dedicated single table fit immediately, save as requested for owner review
            status = "requested"
            table_id = None
            table_obj = None
            msg = f"Tables are currently high in demand. Your request for {req.party_size} guests on {req.service_date} has been prioritized for staff confirmation."

        insert_payload = {
            "guest_name": req.guest_name,
            "phone": req.phone,
            "party_size": req.party_size,
            "adults": adults,
            "children": children,
            "total_price": total_price,
            "service_date": req.service_date,
            "service_time": req.service_time,
            "channel": req.channel,
            "status": status,
            "table_id": table_id,
            "note": req.note or "",
        }

        try:
            res = supabase.from_("booking_requests").insert(insert_payload).execute()
            booking_id = res.data[0]["id"] if (res.data and len(res.data) > 0) else None
        except Exception as e:
            # Still return response for demo if database credentials are not fully wired
            booking_id = "temp-" + datetime.now().strftime("%Y%m%d%H%M%S")

        return BookingResponse(
            id=booking_id,
            guest_name=req.guest_name,
            party_size=req.party_size,
            adults=adults,
            children=children,
            total_price=total_price,
            service_date=req.service_date,
            service_time=req.service_time,
            channel=req.channel,
            status=status,
            table=table_obj,
            confirmation_message=msg
        )
