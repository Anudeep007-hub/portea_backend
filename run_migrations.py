"""Run the project SQL migrations in order.

Usage from the backend folder:
    vir\Scripts\python.exe run_migrations.py
"""
import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


MIGRATION_FILES = [
    "002_physio_choice.sql",
    "003_appointment_activity.sql",
]


async def run_migrations():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from backend/.env")

    connection = await asyncpg.connect(database_url)
    
    try:
        for filename in MIGRATION_FILES:
            sql = (Path(__file__).parent / "migrations" / filename).read_text()
            await connection.execute(sql)
            print(f"Applied {filename}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
