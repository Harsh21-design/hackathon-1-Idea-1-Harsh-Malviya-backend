from fastapi import APIRouter, HTTPException
from app.models.booking import BookingCreateRequest, BookingResponse
from app.services.booking_service import AvailabilityEngine
from app.db.supabase import get_supabase_client

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])

@router.post("", response_model=BookingResponse)
def create_booking(booking_in: BookingCreateRequest):
    """
    Submits a booking request from Web Form or API.
    Instantly validates availability and auto-allocates an optimal table.
    """
    try:
        res = AvailabilityEngine.process_booking(booking_in)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
def list_bookings():
    """Returns active booking requests from database."""
    try:
        supabase = get_supabase_client()
        res = supabase.from_("booking_requests").select("*").order("service_date").execute()
        return res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
