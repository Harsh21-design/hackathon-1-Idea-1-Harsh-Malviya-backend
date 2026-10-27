from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class BookingCreate(BaseModel):
    user_id: str = Field(..., description="Supabase auth UID of the user making the booking")
    table_id: int = Field(..., description="ID of the restaurant table requested")
    booking_time: datetime = Field(..., description="Desired booking start datetime (ISO 8601)")
    party_size: int = Field(..., gt=0, description="Number of guests")
    channel: Literal["web", "telegram"] = Field(..., description="Source of the booking request")
    special_requests: Optional[str] = Field(None, description="Any additional notes")

class BookingResponse(BaseModel):
    booking_id: int
    status: Literal["confirmed", "rejected", "pending"]
    message: str
    allocated_table: Optional[int] = None
    scheduled_time: Optional[datetime] = None
