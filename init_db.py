"""
Database initialization and population script for the 5G Slice Manager.
This script creates all necessary tables and populates them with sample data.
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.database import Base, async_engine, sync_engine, async_session_factory as AsyncSessionLocal
from app.db.models import Slice, SliceKPI, Alert, User

# Sample data generation
SLICE_TYPES = ["eMBB", "URLLC", "mMTC", "V2X", "IoT"]
SLICE_STATUSES = ["Active", "Inactive", "Degraded", "Maintenance"]
ALERT_LEVELS = ["info", "warning", "error"]
ALERT_TYPES = ["slice_created", "slice_modified", "device_connect", "alert_triggered", "config_updated"]

def generate_sample_slices() -> List[Dict[str, Any]]:
    """Generate sample slice data matching the mock structure."""
    slices = []
    for i in range(1, 11):
        slice_type = random.choice(SLICE_TYPES)
        status = random.choice(SLICE_STATUSES)
        slices.append({
            'id': f'slice-{i:03d}',
            'name': f'{slice_type} Slice {i}',
            'type': slice_type,
            'status': status,
            'max_throughput': random.uniform(500, 2000),  # Mbps
            'max_latency': random.uniform(1.0, 50.0),    # ms
            'max_devices': random.randint(1000, 10000),
            'description': f'Sample {slice_type} network slice',
            'created_at': datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            'updated_at': datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
        })
    return slices

def generate_sample_kpis(slice_ids: List[str]) -> List[Dict[str, Any]]:
    """Generate sample KPI data for slices."""
    kpis = []
    now = datetime.utcnow()
    
    for slice_id in slice_ids:
        for i in range(24):  # Last 24 hours of data
            timestamp = now - timedelta(hours=i)
            kpis.append({
                'slice_id': slice_id,
                'timestamp': timestamp,
                'latency': random.uniform(1.0, 50.0),
                'throughput': random.uniform(100, 1000),
                'connected_devices': random.randint(10, 5000),
                'packet_loss': random.uniform(0, 5),
                'availability': random.uniform(95, 100),
            })
    return kpis

def generate_sample_alerts(slice_ids: List[str]) -> List[Dict[str, Any]]:
    """Generate sample alert data."""
    alerts = []
    now = datetime.utcnow()
    
    for i in range(20):  # 20 sample alerts
        alert_time = now - timedelta(hours=random.randint(1, 24))
        alert_type = random.choice(ALERT_TYPES)
        level = random.choice(ALERT_LEVELS)
        slice_id = random.choice(slice_ids)
        
        if alert_type == 'slice_created':
            message = f"New slice {slice_id} was created"
        elif alert_type == 'slice_modified':
            message = f"Configuration updated for slice {slice_id}"
        elif alert_type == 'device_connect':
            message = f"New device connected to slice {slice_id}"
        elif alert_type == 'alert_triggered':
            message = f"High latency detected on slice {slice_id}"
        else:
            message = "System configuration updated"
            
        alerts.append({
            'timestamp': alert_time,
            'level': level,
            'message': message,
            'resolved': random.choice([True, False]),
            'resolved_at': alert_time + timedelta(minutes=random.randint(5, 60)) if random.choice([True, False]) else None,
            'entity_type': 'slice',
            'entity_id': slice_id,
            'context': {'severity': level}
        })
    
    return alerts

async def init_models():
    """Create all database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully.")

async def insert_sample_data():
    """Insert sample data into the database."""
    async with AsyncSessionLocal() as session:
        # Add sample slices
        sample_slices = generate_sample_slices()
        for slice_data in sample_slices:
            # Convert datetime strings to datetime objects if needed
            if isinstance(slice_data.get('created_at'), str):
                slice_data['created_at'] = datetime.fromisoformat(slice_data['created_at'])
            if isinstance(slice_data.get('updated_at'), str):
                slice_data['updated_at'] = datetime.fromisoformat(slice_data['updated_at'])
            
            session.add(Slice(**slice_data))
        
        await session.commit()
        print(f"Inserted {len(sample_slices)} sample slices.")
        
        # Get slice IDs for generating related data
        result = await session.execute(text("SELECT id FROM slices"))
        slice_ids = [row[0] for row in result.fetchall()]
        
        # Add sample KPIs
        sample_kpis = generate_sample_kpis(slice_ids)
        for kpi_data in sample_kpis:
            session.add(SliceKPI(**kpi_data))
        
        # Add sample alerts
        sample_alerts = generate_sample_alerts(slice_ids)
        for alert_data in sample_alerts:
            # Convert resolved_at string to datetime if needed
            if alert_data.get('resolved_at') and isinstance(alert_data['resolved_at'], str):
                alert_data['resolved_at'] = datetime.fromisoformat(alert_data['resolved_at'])
            session.add(Alert(**alert_data))
        
        await session.commit()
        print(f"Inserted {len(sample_kpis)} sample KPIs and {len(sample_alerts)} sample alerts.")

async def init_db():
    """Initialize the database with tables and sample data."""
    print("Initializing database...")
    await init_models()
    await insert_sample_data()
    print("Database initialization complete!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
