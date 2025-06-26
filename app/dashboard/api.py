"""
API client for fetching data from the backend.
"""
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
import logging

from .config import API_BASE_URL

logger = logging.getLogger(__name__)

class DashboardAPI:
    """Client for interacting with the dashboard API."""
    
    def __init__(self, base_url: str = None):
        """Initialize the API client."""
        self.base_url = base_url or API_BASE_URL
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get_slice_metrics(self, time_range: str = '1h') -> List[Dict[str, Any]]:
        """Fetch metrics for all slices."""
        url = f"{self.base_url}/api/dashboard/slices/metrics"
        params = {'time_range': time_range}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching slice metrics: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return []
    
    async def get_kpis(self, time_range: str = '1h') -> List[Dict[str, Any]]:
        """Fetch KPIs for all slices."""
        url = f"{self.base_url}/api/dashboard/kpis"
        params = {'time_range': time_range}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching KPIs: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return []
    
    async def get_alerts(self, limit: int = 5, resolved: bool = False) -> List[Dict[str, Any]]:
        """Fetch alerts."""
        url = f"{self.base_url}/api/dashboard/alerts"
        params = {'limit': limit, 'resolved': str(resolved).lower()}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching alerts: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return []
    
    async def get_slice_history(self, slice_id: str, time_range: str = '1h') -> List[Dict[str, Any]]:
        """Fetch historical metrics for a specific slice."""
        url = f"{self.base_url}/api/dashboard/slices/{slice_id}/history"
        params = {'time_range': time_range}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching slice history: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return []

# Singleton instance
api_client = DashboardAPI()

# Helper functions for direct API access
async def get_slice_metrics() -> List[Dict[str, Any]]:
    """Get metrics for all slices."""
    async with DashboardAPI() as client:
        return await client.get_slice_metrics()

async def get_kpis() -> List[Dict[str, Any]]:
    """Get KPIs for all slices."""
    async with DashboardAPI() as client:
        return await client.get_kpis()

async def get_alerts(limit: int = 5) -> List[Dict[str, Any]]:
    """Get active alerts."""
    async with DashboardAPI() as client:
        return await client.get_alerts(limit=limit)

async def get_slice_history(slice_id: str) -> List[Dict[str, Any]]:
    """Get historical metrics for a specific slice."""
    async with DashboardAPI() as client:
        return await client.get_slice_history(slice_id)
