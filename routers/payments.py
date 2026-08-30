from fastapi import APIRouter, HTTPException, Depends, Request


from database import get_db_connection
from schemas.pydantic_models import PaymentOrderCreate
from utils.ids import generate_payment_ref

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/create-order")
async def create_payment_order(payload: PaymentOrderCreate, conn = Depends(get_db_connection)):
    """
    Initiates a payment order for a package booking. 
    Calculates the exact amount based on service price * package size.
    """
    # 1. Fetch the booking and service pricing details
    booking = await conn.fetchrow(
        """
        SELECT b.id AS booking_id, b.package_size, s.price_per_session
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.booking_ref = $1
        """,
        payload.booking_ref
    )
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    # Calculate total amount (e.g. 5 sessions * 1000 = 5000 INR)
    total_amount = booking["package_size"] * booking["price_per_session"]
    payment_ref = generate_payment_ref(payload.booking_ref)
    
    # 2. Save a pending payment record in AlloyDB
    await conn.execute(
        """
        INSERT INTO payments (payment_ref, booking_id, amount, status)
        VALUES ($1, $2, $3, 'Pending')
        """,
        payment_ref, booking["booking_id"], total_amount
    )
    
    # In production, call Razorpay API here to get a real razorpay_order_id
    mock_razorpay_order_id = f"order_{payment_ref}"
    
    return {
        "payment_ref": payment_ref,
        "razorpay_order_id": mock_razorpay_order_id,
        "amount": total_amount,
        "currency": "INR"
    }

@router.post("/webhook")
async def payment_webhook(request: Request, conn = Depends(get_db_connection)):
    """Razorpay background callback confirming transaction success or failure."""
    event_data = await request.json()
    
    # Mock webhook processing logic
    # In production, verify Razorpay signature here using webhook secret
    
    payment_ref = event_data.get("payment_ref")
    status = event_data.get("status") # 'Success' or 'Failed'
    
    if payment_ref:
        await conn.execute(
            "UPDATE payments SET status = $1 WHERE payment_ref = $2",
            status, payment_ref
        )
        
    return {"status": "received"}