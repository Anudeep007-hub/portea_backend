from fastapi import FastAPI, UploadFile, File, Form

app = FastAPI(title="Portea Physio API")

# ==========================================
# 0. AUTHENTICATION (Phone + OTP)
# ==========================================
@app.post("/auth/send-otp")
async def send_otp(phone: str):
    """
    Generate a 4 or 6 digit OTP and send it via SMS (or print for local testing).
    Saves OTP in cache with a 5-min expiry.
    """
    pass

@app.post("/auth/verify-otp")
async def verify_otp(phone: str, otp: str):
    """
    1. Checks if OTP is correct.
    2. Checks database: Does Person exist? 
       - If YES: Log in.
       - If NO: Create Person.
    3. Returns session token and person_ref.
    """
    pass

@app.post("/auth/ops/login")
async def ops_login(username: str, password: str):
    """Simple email/password login for internal Ops team."""
    pass

# ==========================================
# 1. SERVICES (Catalog)
# ==========================================
@app.get("/services")
async def list_services():
    """Fetch all available physiotherapy services and their prices."""
    pass

# ==========================================
# 2. PERSONS (Patients & Relatives)
# ==========================================
@app.post("/persons")
async def create_person():
    """Register a new patient or family member."""
    pass

@app.get("/persons/{person_ref}")
async def get_person_profile(person_ref: str):
    """Get person details and roles."""
    pass

@app.patch("/persons/{person_ref}")
async def update_person_profile(person_ref: str):
    """Update standard details like 'name' or 'age'."""
    pass

@app.post("/persons/{person_ref}/change-phone")
async def request_phone_change(person_ref: str, new_phone: str):
    """Step 1: Send OTP to new phone number."""
    pass

@app.patch("/persons/{person_ref}/verify-phone-change")
async def verify_phone_change(person_ref: str, new_phone: str, otp: str):
    """Step 2: Verify OTP and update phone in database."""
    pass

# ==========================================
# 3. PHYSIOS
# ==========================================
@app.get("/physios")
async def search_physios(pincode: str = None, service_slug: str = None):
    """Find active physios filtered by pincode and specialization."""
    pass

@app.post("/physios")
async def onboard_physio(person_ref: str):
    """Ops/Admin: Upgrade an existing Person record into a Physio."""
    pass

@app.patch("/physios/{person_ref}")
async def update_physio_details(person_ref: str):
    """Update specialization, pincode, or active status."""
    pass

# ==========================================
# 4. BOOKINGS (The Package & Documents)
# ==========================================
@app.post("/bookings")
async def create_booking():
    """Create a package booking and link patient and booker."""
    pass

@app.get("/bookings/{booking_ref}")
async def get_booking_details(booking_ref: str):
    """Fetch package details, payment status, and appointments."""
    pass

@app.patch("/bookings/{booking_ref}/assign-physio")
async def assign_physio_to_booking(booking_ref: str):
    """Ops endpoint: Assign a physio to the booking package."""
    pass

@app.post("/bookings/{booking_ref}/documents")
async def upload_clinical_document(
    booking_ref: str, 
    file: UploadFile = File(...), 
    description: str = Form(None)
):
    """Upload prescription, X-ray, or report files to cloud storage."""
    pass

@app.get("/bookings/{booking_ref}/documents")
async def get_clinical_documents(booking_ref: str):
    """Fetch prescription/document URLs for Ops and Physios to review."""
    pass

# ==========================================
# 5. APPOINTMENTS (The Individual Sessions)
# ==========================================
@app.post("/bookings/{booking_ref}/appointments")
async def schedule_appointment(booking_ref: str):
    """
    Book a slot. Validates 3-hour lead time in API 
    and 1-hour physio gap in AlloyDB. Defaults to 'Pending'.
    """
    pass

@app.patch("/appointments/{appt_ref}/reschedule")
async def reschedule_appointment(appt_ref: str):
    """Change start time and write to status_events audit log."""
    pass

@app.patch("/appointments/{appt_ref}/status")
async def update_appointment_status(appt_ref: str):
    """Mark as 'Completed' or 'Cancelled'."""
    pass

@app.patch("/appointments/{appt_ref}/confirm")
async def confirm_appointment(appt_ref: str, physio_ref: str = None):
    """Ops endpoint: Change status from 'Pending' to 'Confirmed'."""
    pass

# ==========================================
# 6. PAYMENTS (Gateway Integration)
# ==========================================
@app.post("/payments/create-order")
async def create_payment_order(booking_ref: str):
    """Initiates a Razorpay order for a booking before the user pays."""
    pass

@app.post("/payments/webhook")
async def payment_webhook():
    """Razorpay background callback confirming success or failure."""
    pass