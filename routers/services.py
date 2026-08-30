from fastapi import APIRouter, Depends


from database import get_db_connection

router = APIRouter(prefix="/services", tags=["Services Catalog"])

@router.get("")
async def list_services(conn = Depends(get_db_connection)):
    """Fetch all available physiotherapy services, slugs, and pricing."""
    services = await conn.fetch("SELECT id, slug, name, description, price_per_session FROM services")
    return [dict(s) for s in services]