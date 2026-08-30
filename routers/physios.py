from fastapi import APIRouter, HTTPException, Depends


from database import get_db_connection
from schemas.pydantic_models import PhysioOnboard, PhysioUpdate

router = APIRouter(prefix="/physios", tags=["Physiotherapists"])

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