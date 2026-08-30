from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import connect_db, close_db
from routers import auth, persons, services, physios, bookings, appointments, payments, ops

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup: Connect to AlloyDB ---
    await connect_db()
    yield
    # --- Shutdown: Close database pool ---
    await close_db()

app = FastAPI(
    title="Portea Physio API",
    description="Backend service for Portea Physiotherapy booking engine powered by FastAPI & AlloyDB",
    version="1.0.0",
    lifespan=lifespan
)

# Mount all routers
app.include_router(auth.router)
app.include_router(persons.router)
app.include_router(services.router)
app.include_router(physios.router)
app.include_router(bookings.router)
app.include_router(appointments.router)
app.include_router(payments.router)
app.include_router(ops.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Portea Physio API. Server is live and healthy."}