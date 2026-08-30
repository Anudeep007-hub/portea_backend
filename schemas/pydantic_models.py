from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ==========================================
# 0. AUTH SCHEMAS
# ==========================================
class SendOTPRequest(BaseModel):
    phone: str = Field(..., example="9876543210")

class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., example="9876543210")
    otp: str = Field(..., example="4829")

class OpsLoginRequest(BaseModel):
    username: str
    password: str

# ==========================================
# 2. PERSON & PROFILE SCHEMAS
# ==========================================
class PersonCreate(BaseModel):
    name: str = Field(..., max_length=120)
    phone: str = Field(..., max_length=15)
    age: Optional[int] = Field(None, ge=0, le=120)

class PersonUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    age: Optional[int] = Field(None, ge=0, le=120)

class PhoneChangeRequest(BaseModel):
    new_phone: str = Field(..., max_length=15)

class PhoneVerifyRequest(BaseModel):
    new_phone: str
    otp: str

# ==========================================
# 3. PHYSIO SCHEMAS
# ==========================================
class PhysioOnboard(BaseModel):
    person_ref: str = Field(..., example="PS_4F9K2X1A")
    specialization: str = Field(..., max_length=80)
    service_pincode: str = Field(..., max_length=10)

class PhysioUpdate(BaseModel):
    specialization: Optional[str] = None
    service_pincode: Optional[str] = None
    active: Optional[bool] = None

# ==========================================
# 4. BOOKING & DOCUMENT SCHEMAS
# ==========================================
class BookingCreate(BaseModel):
    patient_ref: str = Field(..., example="PS_PAT001")
    booked_by_ref: str = Field(..., example="PS_REL001")
    service_id: int
    package_size: int = Field(1, description="1, 5, or 10 sessions")
    address_line: str
    pincode: str = Field(..., max_length=10)
    condition_notes: Optional[str] = None

class DocumentDescription(BaseModel):
    description: Optional[str] = Field(None, description="e.g., Knee X-Ray report")

# ==========================================
# 5. APPOINTMENT SCHEMAS
# ==========================================
class AppointmentCreate(BaseModel):
    session_number: int
    start_at: datetime = Field(..., description="Wall-clock time format: YYYY-MM-DDTHH:MM:SS")
    duration_minutes: int = Field(45, description="Default is 45 mins")

class AppointmentStatusUpdate(BaseModel):
    status: str = Field(..., description="Must be 'Completed' or 'Cancelled'")
    note: Optional[str] = None

class AppointmentConfirm(BaseModel):
    physio_ref: Optional[str] = Field(None, description="Optional if physio wasn't assigned yet")

# ==========================================
# 6. PAYMENT SCHEMAS
# ==========================================
class PaymentOrderCreate(BaseModel):
    booking_ref: str = Field(..., example="BK_7H2M9K3P")