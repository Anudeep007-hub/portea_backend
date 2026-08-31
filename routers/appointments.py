from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
import asyncpg

from database import get_db_connection
from schemas.pydantic_models import AppointmentCreate, AppointmentStatusUpdate
from utils.ids import generate_appt_ref
from utils.security import get_current_patient


router = APIRouter(prefix="", tags=["Appointments"])

@router.post("/bookings/{booking_ref}/appointments")
async def schedule_appointment(
    booking_ref: str,
    payload: AppointmentCreate,
    person_ref: str = Depends(get_current_patient),
    conn = Depends(get_db_connection),
):
    """Schedule the next unused package session, with one extra pre-book allowed."""
    min_allowed_time = datetime.now() + timedelta(hours=3)
    if payload.start_at < min_allowed_time:
        raise HTTPException(
            status_code=400, 
            detail="Appointments must be booked at least 3 hours in advance."
        )
        
    try:
        async with conn.transaction():
            booking = await conn.fetchrow(
            """
            SELECT b.id, b.patient_id, b.package_size, b.physio_choice, b.preferred_physio_id
            FROM bookings b JOIN persons booker ON booker.id = b.booked_by_id
            WHERE b.booking_ref = $1 AND booker.person_ref = $2 FOR UPDATE
            """,
            booking_ref,
            person_ref,
            )
            if not booking:
                raise HTTPException(status_code=404, detail="Booking not found")

            active = await conn.fetchval(
            """
            SELECT COUNT(*) FROM appointments
            WHERE booking_id = $1
              AND start_at > now()
              AND status IN ('Pending', 'Confirmed', 'Scheduled')
            """,
            booking["id"],
        )
            if active >= 2:
                raise HTTPException(
                status_code=409,
                    detail="Your current session and one extra session are already booked.",
            )

            next_session = await conn.fetchval(
            """
            SELECT COALESCE(MIN(number), $2 + 1)
            FROM generate_series(1, $2) AS number
            WHERE NOT EXISTS (
                SELECT 1 FROM appointments
                WHERE booking_id = $1
                  AND session_number = number
                  AND status <> 'Cancelled'
            )
            """,
            booking["id"],
            booking["package_size"],
        )
            if next_session > booking["package_size"]:
                raise HTTPException(status_code=409, detail="All package sessions have been used.")
            if payload.session_number != next_session:
                raise HTTPException(status_code=409, detail=f"The next eligible session is {next_session}.")

            appt_ref = generate_appt_ref(booking_ref)
            await conn.fetchval(
            """
            INSERT INTO appointments (
                appt_ref, booking_id, patient_id, physio_id,
                session_number, start_at, duration_minutes, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'Pending')
            RETURNING id
            """,
            appt_ref, booking["id"], booking["patient_id"], booking["preferred_physio_id"],
            payload.session_number, payload.start_at, payload.duration_minutes
        )
            appointment_id = await conn.fetchval(
                "SELECT id FROM appointments WHERE appt_ref = $1",
                appt_ref,
            )
            await conn.execute(
                """
                INSERT INTO appointment_activity (appointment_id, actor_type, action, details)
                VALUES ($1, 'Patient', 'Requested appointment', 'Patient requested this appointment slot.')
                """,
                appointment_id,
            )
    
    except asyncpg.exceptions.ExclusionViolationError:
        raise HTTPException(
            status_code=409,
            detail="This physiotherapist is no longer available at that time. Please choose another slot.",
        )
    except asyncpg.exceptions.CheckViolationError as e:
        if "physio_buffer_range" in str(e):
            raise HTTPException(status_code=409, detail="Time slot conflicts with another physio session.")
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"message": "Appointment requested successfully", "appt_ref": appt_ref, "status": "Pending"}

@router.patch("/appointments/{appt_ref}/reschedule")
async def reschedule_appointment(
    appt_ref: str,
    payload: AppointmentCreate,
    person_ref: str = Depends(get_current_patient),
    conn = Depends(get_db_connection),
):
    """Reschedule an appointment start time."""
    appt = await conn.fetchrow(
        """
        SELECT a.id, a.status, a.start_at FROM appointments a
        JOIN bookings b ON b.id = a.booking_id JOIN persons booker ON booker.id = b.booked_by_id
        WHERE a.appt_ref = $1 AND booker.person_ref = $2
        """,
        appt_ref, person_ref,
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt["status"] in ("Cancelled", "Completed") or appt["start_at"] <= datetime.now():
        raise HTTPException(status_code=409, detail="Only an upcoming appointment can be rescheduled.")
        
    try:
        await conn.execute(
            "UPDATE appointments SET start_at = $1, updated_at = now() WHERE appt_ref = $2",
            payload.start_at, appt_ref
        )
    except asyncpg.exceptions.PostgresError as e:
        raise HTTPException(status_code=409, detail="Selected slot is unavailable or conflicts with buffer rules.")

    await conn.execute(
        """
        INSERT INTO appointment_activity (appointment_id, actor_type, actor_ref, action, details)
        VALUES ($1, 'Patient', $2, 'Rescheduled appointment', 'Patient selected a new appointment date and time.')
        """,
        appt["id"],
        person_ref,
    )
        
    return {"message": "Appointment rescheduled successfully"}

@router.patch("/appointments/{appt_ref}/status")
async def update_appointment_status(
    appt_ref: str,
    payload: AppointmentStatusUpdate,
    person_ref: str = Depends(get_current_patient),
    conn = Depends(get_db_connection),
):
    """Mark appointment as 'Completed' or 'Cancelled'."""
    if payload.status not in ("Completed", "Cancelled"):
        raise HTTPException(status_code=400, detail="Status must be Completed or Cancelled.")
    appt = await conn.fetchrow(
        """
        SELECT a.id, a.status FROM appointments a
        JOIN bookings b ON b.id = a.booking_id JOIN persons booker ON booker.id = b.booked_by_id
        WHERE a.appt_ref = $1 AND booker.person_ref = $2
        """,
        appt_ref, person_ref,
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt["status"] in ("Completed", "Cancelled"):
        raise HTTPException(
            status_code=409,
            detail="A completed or cancelled appointment cannot be changed.",
        )
        
    await conn.execute(
        "UPDATE appointments SET status = $1, updated_at = now() WHERE appt_ref = $2",
        payload.status, appt_ref
    )
    await conn.execute(
        """
        INSERT INTO appointment_activity (appointment_id, actor_type, actor_ref, action, details)
        VALUES ($1, 'Patient', $2, $3, 'Patient changed this appointment status.')
        """,
        appt["id"],
        person_ref,
        f"Marked appointment as {payload.status}",
    )
    return {"message": f"Appointment status updated to {payload.status}"}
