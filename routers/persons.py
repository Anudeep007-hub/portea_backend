from fastapi import APIRouter, HTTPException, Depends


from database import get_db_connection
from schemas.pydantic_models import PersonUpdate, PhoneChangeRequest, PhoneVerifyRequest
from utils.security import make_otp, verify_otp

router = APIRouter(prefix="/persons", tags=["Persons & Profiles"])

@router.get("/{person_ref}")
async def get_person_profile(person_ref: str, conn = Depends(get_db_connection)):
    """Fetch profile details and verify if they are registered as a physio."""
    person = await conn.fetchrow("SELECT * FROM persons WHERE person_ref = $1", person_ref)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
        
    # Check if this person is also a physio
    physio = await conn.fetchrow("SELECT * FROM physios WHERE person_id = $1", person["id"])
    
    return {
        "person_ref": person["person_ref"],
        "name": person["name"],
        "phone": person["phone"],
        "age": person["age"],
        "is_physio": physio is not None,
        "physio_details": dict(physio) if physio else None,
        "created_at": person["created_at"]
    }

@router.patch("/{person_ref}")
async def update_person_profile(person_ref: str, payload: PersonUpdate, conn = Depends(get_db_connection)):
    """Update name or age."""
    person = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", person_ref)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
        
    await conn.execute(
        """
        UPDATE persons 
        SET name = COALESCE($1, name), 
            age = COALESCE($2, age), 
            updated_at = now()
        WHERE person_ref = $3
        """,
        payload.name, payload.age, person_ref
    )
    return {"message": "Profile updated successfully"}

@router.post("/{person_ref}/change-phone")
async def request_phone_change(person_ref: str, payload: PhoneChangeRequest, conn = Depends(get_db_connection)):
    """Step 1: Sends an OTP to the NEW phone number to verify ownership."""
    new_phone = payload.new_phone
    
    # Check if the new phone is already taken by someone else
    existing = await conn.fetchrow("SELECT id FROM persons WHERE phone = $1", new_phone)
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered to another account")
        
    otp = make_otp(new_phone, purpose="change-phone")
    
    print(f"\n================================")
    print(f" [PHONE CHANGE OTP] New Phone: {new_phone} | OTP: {otp}")
    print(f"================================\n")
    
    return {"message": "OTP sent to new phone number", "debug_otp": otp}

@router.patch("/{person_ref}/verify-phone-change")
async def verify_phone_change(person_ref: str, payload: PhoneVerifyRequest, conn = Depends(get_db_connection)):
    """Step 2: Verifies the OTP sent to the new phone and updates the database."""
    new_phone = payload.new_phone
    entered_otp = payload.otp
    
    if not verify_otp(new_phone, entered_otp, purpose="change-phone"):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    await conn.execute(
        "UPDATE persons SET phone = $1, updated_at = now() WHERE person_ref = $2",
        new_phone, person_ref
    )
    
    return {"message": "Phone number successfully updated"}
