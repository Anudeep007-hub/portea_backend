from datetime import datetime, timedelta

import asyncpg
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from database import get_db_connection


from schemas.pydantic_models import BookingCreate, BookingWithFirstAppointment
from utils.ids import generate_appt_ref, generate_booking_ref
from utils.security import get_current_patient
from storage import upload_booking_document

router = APIRouter(prefix="/bookings", tags=["Bookings & Documents"])


async def create_booking_record(conn, payload: BookingCreate, person_ref: str):
    """Create the package record and return the values needed for a session."""
    if payload.booked_by_ref != person_ref:
        raise HTTPException(
            status_code=403,
            detail="You can only create bookings from your own signed-in account.",
        )

    patient = await conn.fetchrow(
        "SELECT id FROM persons WHERE person_ref = $1",
        payload.patient_ref,
    )
    booker = await conn.fetchrow(
        "SELECT id FROM persons WHERE person_ref = $1",
        payload.booked_by_ref,
    )
    if not patient or not booker:
        raise HTTPException(status_code=404, detail="Patient or Booker person_ref not found")

    service = await conn.fetchrow(
        "SELECT id, price_per_session FROM services WHERE id = $1",
        payload.service_id,
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    preferred_physio_id = None
    if payload.physio_choice == "PREFERRED_PHYSIO":
        if not payload.preferred_physio_ref:
            raise HTTPException(status_code=400, detail="Please choose a physiotherapist.")

        physio = await conn.fetchrow(
            """
            SELECT physio.person_id
            FROM physios physio
            JOIN persons person ON person.id = physio.person_id
            WHERE person.person_ref = $1
              AND physio.active = TRUE
              AND physio.service_pincode = $2
            """,
            payload.preferred_physio_ref,
            payload.pincode,
        )
        if not physio:
            raise HTTPException(
                status_code=400,
                detail="This physiotherapist is not available for the selected pincode.",
            )
        preferred_physio_id = physio["person_id"]

    booking_ref = generate_booking_ref(payload.booked_by_ref)
    total_price = float(service["price_per_session"]) * int(payload.package_size)
    booking_id = await conn.fetchval(
        """
        INSERT INTO bookings (
            booking_ref, patient_id, booked_by_id, service_id,
            package_size, price_total, address_line, pincode, condition_notes,
            physio_choice, preferred_physio_id, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'New')
        RETURNING id
        """,
        booking_ref,
        patient["id"],
        booker["id"],
        payload.service_id,
        payload.package_size,
        total_price,
        payload.address_line,
        payload.pincode,
        payload.condition_notes,
        payload.physio_choice,
        preferred_physio_id,
    )

    return {
        "booking_id": booking_id,
        "booking_ref": booking_ref,
        "patient_id": patient["id"],
        "preferred_physio_id": preferred_physio_id,
        "price_total": total_price,
    }


@router.post("/with-first-appointment")
async def create_booking_with_first_appointment(
    payload: BookingWithFirstAppointment,
    person_ref: str = Depends(get_current_patient),
    conn=Depends(get_db_connection),
):
    """Save a new package and its first appointment as one all-or-nothing action."""
    if payload.start_at < datetime.now() + timedelta(hours=3):
        raise HTTPException(
            status_code=400,
            detail="Appointments must be booked at least 3 hours in advance.",
        )

    try:
        async with conn.transaction():
            booking = await create_booking_record(conn, payload, person_ref)
            appt_ref = generate_appt_ref(booking["booking_ref"])
            appointment_id = await conn.fetchval(
                """
                INSERT INTO appointments (
                    appt_ref, booking_id, patient_id, physio_id,
                    session_number, start_at, duration_minutes, status
                )
                VALUES ($1, $2, $3, $4, 1, $5, $6, 'Pending')
                RETURNING id
                """,
                appt_ref,
                booking["booking_id"],
                booking["patient_id"],
                booking["preferred_physio_id"],
                payload.start_at,
                payload.duration_minutes,
            )
            await conn.execute(
                """
                INSERT INTO appointment_activity (appointment_id, actor_type, actor_ref, action, details)
                VALUES ($1, 'Patient', $2, 'Requested appointment', 'Patient requested the first appointment.')
                """,
                appointment_id,
                person_ref,
            )
    except asyncpg.exceptions.ExclusionViolationError:
        raise HTTPException(
            status_code=409,
            detail="This physiotherapist is no longer available at that time. Please choose another slot.",
        )

    return {
        "message": "Booking and first appointment created successfully",
        "booking_ref": booking["booking_ref"],
        "booking_id": booking["booking_id"],
        "appt_ref": appt_ref,
        "price_total": booking["price_total"],
    }


@router.get("/patient/mine")
async def get_my_bookings(person_ref: str = Depends(get_current_patient), conn = Depends(get_db_connection)):
    """Return bookings made by this signed-in patient, including family bookings."""
    rows = await conn.fetch(
        """
        SELECT b.booking_ref, b.package_size, b.price_total, b.status, b.physio_choice,
               b.address_line, b.pincode, b.condition_notes, b.created_at,
               s.name AS service_name, p_pat.name AS patient_name,
               p_pref.person_ref AS preferred_physio_ref, p_pref.name AS preferred_physio_name
        FROM bookings b
        JOIN persons booker ON booker.id = b.booked_by_id
        JOIN persons p_pat ON p_pat.id = b.patient_id
        JOIN services s ON s.id = b.service_id
        LEFT JOIN persons p_pref ON p_pref.id = b.preferred_physio_id
        WHERE booker.person_ref = $1
        ORDER BY b.created_at DESC
        """,
        person_ref,
    )
    booking_refs = [row["booking_ref"] for row in rows]
    appointments = await conn.fetch(
        """
        SELECT a.appt_ref, a.session_number, a.start_at, a.status, b.booking_ref
        FROM appointments a JOIN bookings b ON b.id = a.booking_id
        WHERE b.booking_ref = ANY($1::text[])
        ORDER BY a.session_number
        """,
        booking_refs,
    ) if booking_refs else []
    sessions_by_booking = {reference: [] for reference in booking_refs}
    for appointment in appointments:
        sessions_by_booking[appointment["booking_ref"]].append(dict(appointment))
    return {"bookings": [{**dict(row), "appointments": sessions_by_booking[row["booking_ref"]]} for row in rows]}

@router.post("")
async def create_booking(
    payload: BookingCreate,
    person_ref: str = Depends(get_current_patient),
    conn = Depends(get_db_connection),
):
    """Create a new package booking (e.g., 5 sessions) linking patient and booker."""
    if payload.booked_by_ref != person_ref:
        raise HTTPException(status_code=403, detail="You can only create bookings from your own signed-in account.")

    # 1. Resolve patient and booked_by references to internal IDs
    patient = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", payload.patient_ref)
    booker = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", payload.booked_by_ref)

    if not patient or not booker:
        raise HTTPException(status_code=404, detail="Patient or Booker person_ref not found")

    service = await conn.fetchrow(
        "SELECT id, price_per_session FROM services WHERE id = $1",
        payload.service_id,
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    preferred_physio_id = None
    if payload.physio_choice == "PREFERRED_PHYSIO":
        if not payload.preferred_physio_ref:
            raise HTTPException(status_code=400, detail="Please choose a physiotherapist.")
        physio = await conn.fetchrow(
            """
            SELECT ph.person_id
            FROM physios ph
            JOIN persons p ON p.id = ph.person_id
            WHERE p.person_ref = $1 AND ph.active = TRUE AND ph.service_pincode = $2
            """,
            payload.preferred_physio_ref,
            payload.pincode,
        )
        if not physio:
            raise HTTPException(
                status_code=400,
                detail="This physiotherapist is not available for the selected pincode.",
            )
        preferred_physio_id = physio["person_id"]

    booking_ref = generate_booking_ref(payload.booked_by_ref)
    total_price = float(service["price_per_session"]) * int(payload.package_size)

    # 2. Insert booking record
    booking_id = await conn.fetchval(
        """
        INSERT INTO bookings (
            booking_ref, patient_id, booked_by_id, service_id,
            package_size, price_total, address_line, pincode, condition_notes,
            physio_choice, preferred_physio_id, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'New')
        RETURNING id
        """,
        booking_ref,
        patient["id"],
        booker["id"],
        payload.service_id,
        payload.package_size,
        total_price,
        payload.address_line,
        payload.pincode,
        payload.condition_notes,
        payload.physio_choice,
        preferred_physio_id,
    )

    return {
        "message": "Booking package created successfully",
        "booking_ref": booking_ref,
        "booking_id": booking_id,
        "price_total": total_price,
    }

@router.get("/{booking_ref}")
async def get_booking_details(booking_ref: str, conn = Depends(get_db_connection)):
    """Fetch package details, associated appointments, and documents."""
    booking = await conn.fetchrow(
        """
        SELECT b.*, s.name AS service_name, s.price_per_session,
               p_pat.name AS patient_name, p_book.name AS booked_by_name,
               p_pref.person_ref AS preferred_physio_ref,
               p_pref.name AS preferred_physio_name
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        JOIN persons p_pat ON b.patient_id = p_pat.id
        JOIN persons p_book ON b.booked_by_id = p_book.id
        LEFT JOIN persons p_pref ON b.preferred_physio_id = p_pref.id
        WHERE b.booking_ref = $1
        """,
        booking_ref
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    appointments = await conn.fetch(
        "SELECT * FROM appointments WHERE booking_id = $1", booking["id"]
    )
    documents = await conn.fetch(
        "SELECT * FROM booking_documents WHERE booking_id = $1", booking["id"]
    )
    
    return {
        "booking": dict(booking),
        "appointments": [dict(a) for a in appointments],
        "documents": [dict(d) for d in documents]
    }

@router.post("/{booking_ref}/documents")
async def upload_clinical_document(
    booking_ref: str, 
    file: UploadFile = File(...), 
    description: str = Form(None),
    conn = Depends(get_db_connection)
):
    """Upload prescription, X-ray, or report files for the booking."""
    booking = await conn.fetchrow("SELECT id FROM bookings WHERE booking_ref = $1", booking_ref)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Documents must be 5 MB or smaller.")

    allowed_types = {"application/pdf", "image/jpeg", "image/png"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Upload a PDF, JPG, or PNG document.")

    content = await file.read()
    try:
        storage_url = upload_booking_document(
            booking_ref,
            file.filename,
            content,
            file.content_type,
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail="Document storage is unavailable. Please try again later.") from error
    
    await conn.execute(
        """
        INSERT INTO booking_documents (booking_id, file_url, description)
        VALUES ($1, $2, $3)
        """,
        booking["id"], storage_url, description
    )
    
    return {"message": "Document uploaded successfully", "file_url": storage_url}

@router.get("/{booking_ref}/documents")
async def get_clinical_documents(booking_ref: str, conn = Depends(get_db_connection)):
    """Fetch document URLs attached to this booking."""
    booking = await conn.fetchrow("SELECT id FROM bookings WHERE booking_ref = $1", booking_ref)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    docs = await conn.fetch("SELECT * FROM booking_documents WHERE booking_id = $1", booking["id"])
    return [dict(d) for d in docs]
