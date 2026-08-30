import hashlib
import time

def _generate_ref(prefix: str, unique_identifier: str) -> str:
    """
    Generates a unique reference ID by hashing user data and nanoseconds.
    Example: PS_4F8A9B2C
    """
    raw_data = f"{unique_identifier}-{time.time_ns()}"
    full_hash = hashlib.sha256(raw_data.encode()).hexdigest()
    short_hash = full_hash[:8].upper()
    return f"{prefix}_{short_hash}"

def generate_person_ref(phone: str) -> str:
    return _generate_ref("PS", phone)

def generate_booking_ref(phone: str) -> str:
    return _generate_ref("BK", phone)

def generate_appt_ref(phone: str) -> str:
    return _generate_ref("AP", phone)

def generate_payment_ref(phone: str) -> str:
    return _generate_ref("PY", phone)