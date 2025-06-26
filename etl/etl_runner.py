import asyncio
import logging
import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from etl.extract import fetch_ns3_metrics
from etl.transform import filter_kpi_data
from etl.load import load_kpis_to_db
from app.db.database import async_session_factory as AsyncSessionLocal
from etl.config import NS3_API_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_etl():
    """
    Runs the full ETL pipeline: Extract, Transform, Load.
    """
    logger.info("Starting ETL pipeline run...")
    try:
        raw_data = await fetch_ns3_metrics(NS3_API_URL)
        if not raw_data:
            logger.info("No data extracted. ETL run concluding.")
            return

        kpis = filter_kpi_data(raw_data)
        
        if kpis:
            async with AsyncSessionLocal() as session:
                await load_kpis_to_db(kpis, session)
        else:
            logger.info("No valid KPI data to load after transformation.")
            
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}", exc_info=True)
    
    logger.info("ETL pipeline run finished.")

if __name__ == "__main__":
    # This allows running the ETL process manually via `python -m etl.etl_runner`
    asyncio.run(run_etl())
