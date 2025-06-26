import httpx
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def fetch_ns3_metrics(api_url: str) -> List[Dict[str, Any]]:
    """
    Asynchronously fetches real-time KPI metrics from the NS-3 simulator API.
    Uses httpx for async HTTP requests.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error fetching data from {api_url}: {e}")
        return []
