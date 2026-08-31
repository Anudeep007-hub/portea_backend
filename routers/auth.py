import asyncio
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException

from database import db
from schemas.pydantic_models import OpsLoginRequest, SendOTPRequest, VerifyOTPRequest
from utils.ids import generate_person_ref
from utils.security import create_ops_token, create_patient_token, get_current_patient


router = APIRouter(prefix="/auth", tags=["Authentication"])

# Demo OTP: same code for every user, as requested.
DEMO_OTP = "482913"


def send_twilio_sms(phone: str) -> None:
    """Send the fixed demo OTP to the mobile number entered in the app."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    sender_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not account_sid or not auth_token or not sender_number:
        raise RuntimeError("Add the three Twilio settings to backend/.env first.")

    from twilio.rest import Client

    client = Client(account_sid, auth_token)
    client.messages.create(
        to=f"+91{phone}",
        from_=sender_number,
        body=f"sms_2fa",
    )


@router.post("/send-otp")
async def send_otp(payload: SendOTPRequest):
    """Send the single fixed demo OTP through Twilio."""
    try:
        await asyncio.to_thread(send_twilio_sms, payload.phone)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {"message": "OTP sent successfully"}


@router.post("/resend-otp")
async def resend_otp(payload: SendOTPRequest):
    """Send the same fixed OTP to the same entered mobile number."""
    return await send_otp(payload)


@router.post("/verify-otp")
async def verify_otp(payload: VerifyOTPRequest):
    """Accept only the one demo OTP, then create the patient login session."""
    if not hmac.compare_digest(payload.otp, DEMO_OTP):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    phone = payload.phone

    if not db.pool:
        person_ref = generate_person_ref(phone)
        return {
            "message": "OTP verified. Database is offline, so this is a temporary profile.",
            "person_ref": person_ref,
            "is_new_user": True,
            "access_token": create_patient_token(person_ref),
        }

    async with db.pool.acquire() as conn:
        person = await conn.fetchrow(
            "SELECT person_ref FROM persons WHERE phone = $1",
            phone,
        )

        if person:
            person_ref = person["person_ref"]
            is_new_user = False
        else:
            person_ref = generate_person_ref(phone)
            default_name = f"User_{phone[-4:]}"
            await conn.execute(
                "INSERT INTO persons (person_ref, name, phone) VALUES ($1, $2, $3)",
                person_ref,
                default_name,
                phone,
            )
            is_new_user = True

    return {
        "message": "Login successful",
        "person_ref": person_ref,
        "is_new_user": is_new_user,
        "access_token": create_patient_token(person_ref),
    }


@router.get("/me")
async def current_user(person_ref: str = Depends(get_current_patient)):
    return {"person_ref": person_ref}


@router.post("/ops/login")
async def ops_login(payload: OpsLoginRequest):
    if payload.username == "ops_admin" and payload.password == "portea2026":
        return {
            "message": "Ops login successful",
            "access_token": create_ops_token(payload.username),
        }

    raise HTTPException(status_code=401, detail="Invalid Ops credentials")
