import asyncio
from app.db.database import init_db, async_engine

async def initialize_database():
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(initialize_database())