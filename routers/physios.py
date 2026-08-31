from fastapi import APIRouter, HTTPException, Depends
from datetime import date, datetime, time, timedelta


from database import get_db_connection
from schemas.pydantic_models import PhysioOnboard, PhysioUpdate

router = APIRouter(prefix="/physios", tags=["Physiotherapists"])

SLOT_TIMES = [time(9), time(11), time(14), time(17)]

@router.get("")
async def search_physios(pincode: str = None, service_slug: str = None, conn = Depends(get_db_connection)):
    """Find active physios, optionally filtered by pincode."""
    query = """
        SELECT p.person_ref, p.name, p.phone, ph.specialization, ph.service_pincode, ph.active
        FROM physios ph
        JOIN persons p ON ph.person_id = p.id
        WHERE ph.active = TRUE
    """
    params = []
    
    if pincode:
        params.append(pincode)
        query += f" AND ph.service_pincode = ${len(params)}"
        
    physios = await conn.fetch(query, *params)
    return [dict(physio) for physio in physios]

@router.get("/{person_ref}/availability")
async def physio_availability(person_ref: str, days: int = 60, conn = Depends(get_db_connection)):
    """Return only free dates and time slots for one active physio."""
    physio = await conn.fetchrow(
        """
        SELECT ph.person_id, p.name
        FROM physios ph JOIN persons p ON p.id = ph.person_id
        WHERE p.person_ref = $1 AND ph.active = TRUE
        """,
        person_ref,
    )
    if not physio:
        raise HTTPException(status_code=404, detail="Physiotherapist is unavailable.")

    slots_by_date = {}
    first_day = date.today() + timedelta(days=1)
    for offset in range(min(max(days, 1), 180)):
        current_day = first_day + timedelta(days=offset)
        if current_day.weekday() == 6:  # Sunday
            continue
        available_times = []
        for slot_time in SLOT_TIMES:
            start_at = datetime.combine(current_day, slot_time)
            busy = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM appointments
                    WHERE physio_id = $1
                      AND status IN ('Pending', 'Confirmed', 'Scheduled')
                      AND physio_buffer_range && tsrange(
                          $2::timestamp,
                          $2::timestamp + interval '105 minutes',
                          '[)'
                      )
                )
                """,
                physio["person_id"],
                start_at,
            )
            if not busy:
                hour = slot_time.hour % 12 or 12
                meridiem = "AM" if slot_time.hour < 12 else "PM"
                available_times.append(f"{hour}:{slot_time.minute:02d} {meridiem}")
        if available_times:
            slots_by_date[current_day.isoformat()] = available_times

    return {
        "physio_ref": person_ref,
        "physio_name": physio["name"],
        "dates": list(slots_by_date.keys()),
        "slots": slots_by_date,
    }

@router.post("")
async def onboard_physio(payload: PhysioOnboard, conn = Depends(get_db_connection)):
    """Ops Endpoint: Upgrades an existing Person record into a registered Physio."""
    # 1. Find the person's internal ID using their person_ref
    person = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", payload.person_ref)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found. Register via phone first.")
        
    person_id = person["id"]
    
    # 2. Check if already a physio
    existing_physio = await conn.fetchrow("SELECT person_id FROM physios WHERE person_id = $1", person_id)
    if existing_physio:
        raise HTTPException(status_code=400, detail="This person is already registered as a physio.")
        
    # 3. Insert into physios table
    await conn.execute(
        """
        INSERT INTO physios (person_id, specialization, service_pincode, active)
        VALUES ($1, $2, $3, TRUE)
        """,
        person_id, payload.specialization, payload.service_pincode
    )
    
    return {"message": f"Successfully onboarded {payload.person_ref} as a Physio"}

@router.patch("/{person_ref}")
async def update_physio_details(person_ref: str, payload: PhysioUpdate, conn = Depends(get_db_connection)):
    """Update physio specialization, pincode, or active status (e.g. on leave/resign)."""
    person = await conn.fetchrow("SELECT id FROM persons WHERE person_ref = $1", person_ref)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
        
    await conn.execute(
        """
        UPDATE physios 
        SET specialization = COALESCE($1, specialization),
            service_pincode = COALESCE($2, service_pincode),
            active = COALESCE($3, active)
        WHERE person_id = $4
        """,
        payload.specialization, payload.service_pincode, payload.active, person["id"]
    )
    
    return {"message": "Physio details updated successfully"}
