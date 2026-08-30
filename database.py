import os
import asyncpg
from dotenv import load_dotenv 

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")

class Database:
    pool: asyncpg.Pool = None
    connector = None

db = Database()

async def connect_db():
    global db
    # 1. If running on Cloud Run (using Cloud SQL connector)
    if INSTANCE_CONNECTION_NAME and not DATABASE_URL:
        from google.cloud.sql.connector import create_async_connector
        db.connector = await create_async_connector()
        
        async def getconn():
            return await db.connector.connect_async(
                INSTANCE_CONNECTION_NAME,
                "asyncpg",
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASS", ""),
                db=os.getenv("DB_NAME", "postgres"),
            )
        db.pool = await asyncpg.create_pool(min_size=2, max_size=10, connect=getconn)
        print("Connected via Cloud SQL Python Connector (Cloud Run mode).")
        return

    # 2. If running locally (using direct URL string)
    if DATABASE_URL:
        db.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        print("Connected via direct DATABASE_URL (Local mode).")
        return

    raise ValueError("No database connection configuration found!")

async def close_db():
    if db.pool:
        await db.pool.close()
    if db.connector:
        await db.connector.close_async()
    print("Database connection closed.")

async def get_db_connection():
    async with db.pool.acquire() as connection:
        yield connection