from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from database import get_db_connection


from schemas.pydantic_models import BookingCreate
from utils.ids import generate_booking_ref

router = APIRouter(prefix="/bookings", tags=["Bookings & Documents"])

@router.post("")
async def create_booking(payload: BookingCreate, conn = Depends(get_db_connection)):
    """Create a new package booking (e.g., 5 sessions) linking patient and booker."""
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

    booking_ref = generate_booking_ref(payload.booked_by_ref)
    total_price = float(service["price_per_session"]) * int(payload.package_size)

    # 2. Insert booking record
    booking_id = await conn.fetchval(
        """
        INSERT INTO bookings (
            booking_ref, patient_id, booked_by_id, service_id,
            package_size, price_total, address_line, pincode, condition_notes, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'New')
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
               p_pat.name AS patient_name, p_book.name AS booked_by_name
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        JOIN persons p_pat ON b.patient_id = p_pat.id
        JOIN persons p_book ON b.booked_by_id = p_book.id
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
        
    # In production, upload file to AWS S3 or Google Cloud Storage and get URL
    mock_s3_url = f"https://storage.googleapis.com/portea-mock-bucket/{file.filename}"
    
    await conn.execute(
        """
        INSERT INTO booking_documents (booking_id, file_url, description)
        VALUES ($1, $2, $3)
        """,
        booking["id"], mock_s3_url, description
    )
    
    return {"message": "Document uploaded successfully", "file_url": mock_s3_url}

@router.get("/{booking_ref}/documents")
async def get_clinical_documents(booking_ref: str, conn = Depends(get_db_connection)):
    """Fetch document URLs attached to this booking."""
    booking = await conn.fetchrow("SELECT id FROM bookings WHERE booking_ref = $1", booking_ref)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    docs = await conn.fetch("SELECT * FROM booking_documents WHERE booking_id = $1", booking["id"])
    return [dict(d) for d in docs]