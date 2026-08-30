from fastapi import APIRouter, HTTPException, Depends, status
import random
from datetime import datetime, timedelta


from database import get_db_connection
from schemas.pydantic_models import SendOTPRequest, VerifyOTPRequest, OpsLoginRequest
from utils.ids import generate_person_ref

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory temporary OTP store for MVP: { phone: { "otp": "1234", "expires_at": datetime } }
OTP_CACHE = {}

@router.post("/send-otp")
async def send_otp(payload: SendOTPRequest):
    """Generates a 4-digit OTP and prints it to the console for testing."""
    phone = payload.phone
    otp = str(random.randint(1000, 9999))
    
    # Expires in 5 minutes
    expires_at = datetime.now() + timedelta(minutes=5)
    OTP_CACHE[phone] = {"otp": otp, "expires_at": expires_at}
    
    # In production, integrate an SMS gateway here (e.g., Twilio / Fast2SMS)
    print(f"\n================================")
    print(f" [OTP SERVICE] Phone: {phone} | OTP: {otp}")
    print(f"================================\n")
    
    return {"message": "OTP sent successfully", "debug_otp": otp}  # debug_otp included for easy testing

@router.post("/verify-otp")
async def verify_otp(payload: VerifyOTPRequest, conn = Depends(get_db_connection)):
    """Verifies OTP. If user doesn't exist in AlloyDB, automatically creates them."""
    phone = payload.phone
    entered_otp = payload.otp
    
    # 1. Validate OTP from cache
    record = OTP_CACHE.get(phone)
    if not record or record["otp"] != entered_otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if datetime.now() > record["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP has expired")
    
    # Clear OTP after successful use
    del OTP_CACHE[phone]
    
    # 2. Check if person exists in the database
    person = await conn.fetchrow("SELECT * FROM persons WHERE phone = $1", phone)
    
    if person:
        person_ref = person["person_ref"]
        is_new_user = False
    else:
        # 3. If new, create them automatically
        person_ref = generate_person_ref(phone)
        default_name = f"User_{phone[-4:]}" # Placeholder name until they update profile
        
        await conn.execute(
            """
            INSERT INTO persons (person_ref, name, phone)
            VALUES ($1, $2, $3)
            """,
            person_ref, default_name, phone
        )
        is_new_user = True
        
    # In production, generate a real JWT token here
    return {
        "message": "Login successful",
        "person_ref": person_ref,
        "is_new_user": is_new_user,
        "access_token": f"mock_jwt_token_for_{person_ref}"
    }

@router.post("/ops/login")
async def ops_login(payload: OpsLoginRequest):
    """Simple credentials check for internal Ops team."""
    # Hardcoded for MVP prototype scope
    if payload.username == "ops_admin" and payload.password == "portea2026":
        return {"message": "Ops login successful", "access_token": "mock_ops_admin_token"}
    raise HTTPException(status_code=401, detail="Invalid Ops credentials")