"""Small signed session-token helper for the patient MVP.

Use a long random SESSION_SECRET in production.  This avoids treating a
person reference sent by the browser as proof of identity.
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException


SESSION_SECRET = os.getenv("SESSION_SECRET", "portea-local-development-secret")
SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30
OTP_SECRET = os.getenv("OTP_SECRET", "portea-local-development-otp-secret")
OTP_WINDOW_SECONDS = 5 * 60
OTP_LENGTH = 6


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(subject: str, role: str) -> str:
    payload = {
        "subject": subject,
        "role": role,
        "expires_at": int(time.time()) + SESSION_LIFETIME_SECONDS,
    }
    body = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _encode(hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def create_patient_token(person_ref: str) -> str:
    return create_token(person_ref, "patient")


def create_ops_token(username: str) -> str:
    return create_token(username, "ops")


def make_otp(phone: str, purpose: str = "login", window: int | None = None) -> str:
    """Create a time-based OTP without saving the OTP anywhere."""
    if window is None:
        window = int(time.time() // OTP_WINDOW_SECONDS)

    message = f"{purpose}:{phone}:{window}".encode()
    digest = hmac.new(OTP_SECRET.encode(), message, hashlib.sha256).digest()
    number = int.from_bytes(digest[:8], "big") % (10 ** OTP_LENGTH)
    return f"{number:0{OTP_LENGTH}d}"


def verify_otp(phone: str, entered_otp: str, purpose: str = "login") -> bool:
    """Verify the current OTP or the just-expired window without a cache or DB."""
    if not entered_otp.isdigit() or len(entered_otp) != OTP_LENGTH:
        return False

    current_window = int(time.time() // OTP_WINDOW_SECONDS)
    for window in (current_window, current_window - 1):
        expected_otp = make_otp(phone, purpose, window)
        if hmac.compare_digest(entered_otp, expected_otp):
            return True

    return False


def read_token(token: str, expected_role: str) -> str:
    try:
        body, signature = token.split(".")
        expected = _encode(hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(_decode(body))
        if payload["expires_at"] < time.time():
            raise ValueError("expired")
        if payload["role"] != expected_role:
            raise ValueError("wrong role")
        return payload["subject"]
    except (KeyError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Your sign-in has expired. Please verify your mobile number again.")


async def get_current_patient(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to view your bookings.")
    return read_token(authorization.removeprefix("Bearer ").strip(), "patient")


async def get_current_ops(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to the OPS dashboard.")
    return read_token(authorization.removeprefix("Bearer ").strip(), "ops")
