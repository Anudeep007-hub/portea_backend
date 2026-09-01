from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from database import connect_db, close_db
from routers import auth, persons, services, physios, bookings, appointments, payments, ops

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB in background so uvicorn binds to the port immediately for Cloud Run health checks
    async def init_db():
        try:
            await connect_db()
            app.state.database_ready = True
            print("Database connection established.")
        except Exception as error:
            app.state.database_ready = False
            print(f"Database is unavailable. Running in OTP demo mode: {error}")

    asyncio.create_task(init_db())
    yield
    await close_db()

app = FastAPI(
    title="Portea Physio API",
    description="Backend service for Portea Physiotherapy booking engine powered by FastAPI & AlloyDB",
    version="1.0.0",
    lifespan=lifespan
)

# Allow local dev servers and deployed web frontends.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
