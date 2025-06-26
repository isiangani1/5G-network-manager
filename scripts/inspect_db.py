# scripts/inspect_db.py

import asyncio
import sys
import os

# Add project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.models import Slice, SliceKPI
from app.db.database import async_session_factory as async_session

async def inspect_data():
    async with async_session() as session:
        # Query slices
        slices = (await session.execute(Slice.__table__.select())).fetchall()
        print("== Slices ==")
        for row in slices:
            print(dict(row))

        # Query slice KPIs
        kpis = (await session.execute(SliceKPI.__table__.select())).fetchall()
        print("\n== Slice KPIs ==")
        for row in kpis:
            print(dict(row))



if __name__ == "__main__":
    asyncio.run(inspect_data())
