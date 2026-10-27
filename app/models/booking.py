from pydantic import BaseModel, Field
from typing import Optional, Literal

class TableAllocation(BaseModel):
    table_id: str
    table_name: str
    capacity: int
    section: str

class BookingCreateRequest(BaseModel):
    guest_name: str = Field(..., min_length=2, description="Name of the main contact")
    phone: str = Field(..., min_length=5, description="Phone number with country code")
    party_size: int = Field(..., ge=1, le=35, description="Number of diners (1-35)")
    service_date: str = Field(..., description="YYYY-MM-DD")
    service_time: str = Field(..., description="HH:MM (e.g. 13:30)")
    channel: Literal["web", "telegram"] = "web"
    note: Optional[str] = ""

class BookingResponse(BaseModel):
    id: Optional[str] = None
    guest_name: str
    party_size: int
    service_date: str
    service_time: str
    channel: str
    status: Literal["confirmed", "requested", "declined"]
    table: Optional[TableAllocation] = None
    confirmation_message: str

class ChatMessage(BaseModel):
    role: Literal["user", "model", "system"]
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[list[ChatMessage]] = []
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    booking_created: Optional[BookingResponse] = None
