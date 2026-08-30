from fastapi import APIRouter, HTTPException, Depends


from database import get_db_connection
from schemas.pydantic_models import AppointmentConfirm

router = APIRouter(prefix="/ops", tags=["Ops Control Panel"])

@router.patch("/appointments/{appt_ref}/confirm")
async def confirm_appointment(appt_ref: str, payload: AppointmentConfirm, conn = Depends(get_db_connection)):
    """Ops endpoint: Changes appointment status from 'Pending' to 'Confirmed' and assigns a physio."""
    appt = await conn.fetchrow("SELECT id FROM appointments WHERE appt_ref = $1", appt_ref)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    physio_id = None
    if payload.physio_ref:
        physio_person = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", payload.physio_ref)
        if not physio_person:
            raise HTTPException(status_code=404, detail="Physio person not found")
            
        physio_record = await conn.fetchrow("SELECT person_id FROM physios WHERE person_id = $1", physio_person["id"])
        if not physio_record:
            raise HTTPException(status_code=400, detail="This person is not registered as an active physio")
        physio_id = physio_person["id"]

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
    
    return {"message": "Appointment officially confirmed by Ops", "status": "Confirmed"}