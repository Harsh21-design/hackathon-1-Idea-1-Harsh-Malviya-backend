from pydantic import BaseModel, Field
from typing import Optional, Literal

class TableAllocation(BaseModel):
    table_id: str
    table_name: str
    capacity: int
    section: str

ADULT_PRICE = 45.0   # EUR per adult
CHILD_PRICE = 22.0   # EUR per child (half price, under 12)

class BookingCreateRequest(BaseModel):
    guest_name: str = Field(..., min_length=2, description="Name of the main contact")
    phone: str = Field(..., min_length=5, description="Phone number with country code")
    party_size: int = Field(..., ge=1, le=35, description="Total number of diners (adults + children)")
    adults: int = Field(default=0, ge=0, description="Number of adults (€45 each)")
    children: int = Field(default=0, ge=0, description="Number of children under 12 (€22 each)")
    service_date: str = Field(..., description="YYYY-MM-DD")
    service_time: str = Field(..., description="HH:MM (e.g. 13:30)")
    channel: Literal["web", "telegram"] = "web"
    note: Optional[str] = ""

class BookingResponse(BaseModel):
    id: Optional[str] = None
    guest_name: str
    party_size: int
    adults: int = 0
    children: int = 0
    total_price: float = 0.0
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
