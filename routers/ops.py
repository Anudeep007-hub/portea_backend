from fastapi import APIRouter, HTTPException, Depends


from database import get_db_connection
from schemas.pydantic_models import AppointmentConfirm
from utils.security import get_current_ops

router = APIRouter(prefix="/ops", tags=["Ops Control Panel"])


@router.get("/dashboard")
async def get_ops_dashboard(
    _ops_user: str = Depends(get_current_ops),
    conn = Depends(get_db_connection),
):
    """Return pending appointments and the latest patient/OPS activity."""
    pending = await conn.fetch(
        """
        SELECT a.appt_ref, a.session_number, a.start_at, a.status,
               patient.name AS patient_name, patient.phone AS patient_phone,
               b.booking_ref, b.address_line, b.pincode, b.condition_notes,
               b.physio_choice, service.name AS service_name,
               preferred.person_ref AS preferred_physio_ref,
               preferred.name AS preferred_physio_name
        FROM appointments a
        JOIN bookings b ON b.id = a.booking_id
        JOIN persons patient ON patient.id = a.patient_id
        JOIN services service ON service.id = b.service_id
        LEFT JOIN persons preferred ON preferred.id = b.preferred_physio_id
        WHERE a.status IN ('Pending', 'Confirmed')
        ORDER BY a.start_at
        """
    )

    activity = await conn.fetch(
        """
        SELECT activity.id, activity.action, activity.actor_type, activity.actor_ref,
               activity.details, activity.created_at, appointment.appt_ref,
               booking.booking_ref, patient.name AS patient_name
        FROM appointment_activity activity
        JOIN appointments appointment ON appointment.id = activity.appointment_id
        JOIN bookings booking ON booking.id = appointment.booking_id
        JOIN persons patient ON patient.id = appointment.patient_id
        ORDER BY activity.created_at DESC
        LIMIT 100
        """
    )

    physios = await conn.fetch(
        """
        SELECT person.person_ref, person.name, physio.specialization, physio.service_pincode
        FROM physios physio
        JOIN persons person ON person.id = physio.person_id
        WHERE physio.active = TRUE
        ORDER BY person.name
        """
    )

    unscheduled = await conn.fetch(
        """
        SELECT b.booking_ref, b.created_at, b.address_line, b.pincode,
               patient.name AS patient_name, patient.phone AS patient_phone,
               service.name AS service_name
        FROM bookings b
        JOIN persons patient ON patient.id = b.patient_id
        JOIN services service ON service.id = b.service_id
        WHERE NOT EXISTS (
            SELECT 1 FROM appointments a WHERE a.booking_id = b.id
        )
        ORDER BY b.created_at DESC
        LIMIT 100
        """
    )

    appointments = [dict(row) for row in pending]

    return {
        "pending_appointments": [
            appointment for appointment in appointments if appointment["status"] == "Pending"
        ],
        "appointments": appointments,
        "unscheduled_bookings": [dict(row) for row in unscheduled],
        "activity": [dict(row) for row in activity],
        "physios": [dict(row) for row in physios],
    }


@router.patch("/appointments/{appt_ref}/confirm")
async def confirm_appointment(
    appt_ref: str,
    payload: AppointmentConfirm,
    ops_user: str = Depends(get_current_ops),
    conn = Depends(get_db_connection),
):
    """Ops endpoint: Changes appointment status from 'Pending' to 'Confirmed' and assigns a physio."""
    appt = await conn.fetchrow(
        """
        SELECT a.id, a.physio_id, a.status, b.physio_choice, b.pincode
        FROM appointments a
        JOIN bookings b ON b.id = a.booking_id
        WHERE a.appt_ref = $1
        """,
        appt_ref,
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt["status"] != "Pending":
        raise HTTPException(status_code=409, detail="Only pending appointments can be confirmed.")
        
    physio_id = None
    if payload.physio_ref:
        physio_person = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", payload.physio_ref)
        if not physio_person:
            raise HTTPException(status_code=404, detail="Physio person not found")
            
        physio_record = await conn.fetchrow(
            """
            SELECT person_id FROM physios
            WHERE person_id = $1 AND active = TRUE AND service_pincode = $2
            """,
            physio_person["id"],
            appt["pincode"],
        )
        if not physio_record:
            raise HTTPException(status_code=400, detail="This person is not registered as an active physio")
        physio_id = physio_person["id"]

    if (
        appt["physio_choice"] == "PREFERRED_PHYSIO"
        and physio_id is not None
        and physio_id != appt["physio_id"]
    ):
        raise HTTPException(
            status_code=409,
            detail="This package has a preferred physiotherapist and cannot be reassigned.",
        )

    # Update status to Confirmed and assign physio if provided
    await conn.execute(
        """
        UPDATE appointments 
        SET status = 'Confirmed',
            physio_id = COALESCE($1, physio_id),
            updated_at = now()
        WHERE appt_ref = $2
        """,
        physio_id, appt_ref
    )

    await conn.execute(
        """
        INSERT INTO appointment_activity (appointment_id, actor_type, actor_ref, action, details)
        VALUES ($1, 'OPS', $2, 'Confirmed appointment', 'OPS confirmed the appointment and assigned a physiotherapist.')
        """,
        appt["id"],
        ops_user,
    )
    
    return {"message": "Appointment officially confirmed by Ops", "status": "Confirmed"}
