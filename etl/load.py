from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import SliceKPI
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def load_kpis_to_db(kpi_data: List[Dict[str, Any]], session: AsyncSession):
    """
    Bulk loads a list of transformed KPI data into the slice_kpis table.
    """
    try:
        kpi_objects = [SliceKPI(**item) for item in kpi_data]
        session.add_all(kpi_objects)
        await session.commit()
        logger.info(f"Successfully loaded {len(kpi_objects)} KPI records.")
    except Exception as e:
        logger.error(f"Error loading KPIs to database: {e}", exc_info=True)
        await session.rollback()
        raise
