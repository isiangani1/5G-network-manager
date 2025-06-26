"""
Database Initialization Module

This module contains functions to initialize the database with sample data
for development and testing purposes.
"""

import asyncio
import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

from sqlalchemy import select, func, text, inspect, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from app.db.database import async_engine, async_session_factory as AsyncSessionLocal
from app.db.models import Slice, Device, Metric, Alert, SliceKPI, User

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Sample data generation
SLICE_TYPES = ["eMBB", "URLLC", "mMTC", "V2X", "IoT"]
SLICE_STATUSES = ["Active", "Inactive", "Degraded", "Maintenance"]
ALERT_LEVELS = ["info", "warning", "error"]
ALERT_TYPES = ["slice_created", "slice_modified", "device_connect", "alert_triggered", "config_updated"]

# Default admin user
ADMIN_USER = {
    "username": "admin",
    "email": "admin@5gslice.com",
    "full_name": "Admin User",
    "password": "admin123",  # In production, this should be hashed
    "is_superuser": True,
    "is_active": True
}

async def init_db():
    """Initialize the database by creating all tables."""
    logger.info(f"Initializing database: {SQLALCHEMY_DATABASE_URL}")
    
    # Create all tables
    async with async_engine.begin() as conn:
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")
    try:
        # Test the connection first
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("Database connection successful")
        
        # Create tables
        async with async_engine.begin() as conn:
            print("Dropping existing tables...")
            await conn.run_sync(Base.metadata.drop_all)
            print("Creating new tables...")
            await conn.run_sync(Base.metadata.create_all)
        
        print("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        return False

async def create_sample_data():
    """
    Create sample data for the application.
    
    This function populates the database with sample slices, devices, metrics,
    and alerts for development and testing purposes.
    """
    logger.info("Starting sample data creation...")
    
    async with AsyncSessionLocal() as session:
        # Check if we already have data
        result = await session.execute(select(func.count()).select_from(Slice))
        if result.scalar() > 0:
            logger.info("Sample data already exists. Skipping...")
            return
        
        # Create admin user
        logger.info("Creating admin user...")
        admin = User(
            username=ADMIN_USER["username"],
            email=ADMIN_USER["email"],
            full_name=ADMIN_USER["full_name"],
            hashed_password=User.get_password_hash(ADMIN_USER["password"]),
            is_superuser=ADMIN_USER["is_superuser"],
            is_active=ADMIN_USER["is_active"]
        )
        session.add(admin)
        await session.commit()
        
        # Create sample slices
        logger.info("Creating sample slices...")
        slices = []
        slice_types = ["eMBB", "URLLC", "mMTC", "V2X", "IoT"]
        statuses = ["Active", "Inactive", "Degraded", "Maintenance"]
        
        for i in range(1, 11):
            slice_type = random.choice(slice_types)
            status = random.choice(statuses)
            
            slice_data = {
                "id": f"slice-{i:03d}",
                "name": f"{slice_type} Slice {i}",
                "type": slice_type,
                "status": status,
                "max_throughput": random.uniform(500, 2000),
                "max_latency": random.uniform(1.0, 50.0),
                "max_devices": random.randint(100, 10000),
                "description": f"Sample {slice_type} network slice",
                "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                "updated_at": datetime.utcnow() - timedelta(minutes=random.randint(1, 1440))
            }
            slices.append(Slice(**slice_data))
        
        session.add_all(slices)
        await session.commit()
        
        # Create sample devices
        logger.info("Creating sample devices...")
        devices = []
        device_types = ["UE", "gNB", "UPF", "SMF", "AMF"]
        
        for i in range(1, 51):  # 50 sample devices
            device_type = random.choice(device_types)
            slice_obj = random.choice(slices)
            
            device = Device(
                id=f"dev-{i:03d}",
                name=f"{device_type}-{i:03d}",
                type=device_type,
                status=random.choice(["connected", "disconnected", "error"]),
                ip_address=f"192.168.1.{i}",
                mac_address=f"{random.randint(16, 255):02x}:{random.randint(16, 255):02x}:{random.randint(16, 255):02x}:{random.randint(16, 255):02x}:{random.randint(16, 255):02x}:{random.randint(16, 255):02x}",
                last_seen=datetime.utcnow() - timedelta(minutes=random.randint(1, 1440)),
                slice_id=slice_obj.id
            )
            devices.append(device)
        
        session.add_all(devices)
        await session.commit()
        
        # Create sample metrics
        logger.info("Creating sample metrics...")
        now = datetime.utcnow()
        
        for i in range(24):  # Last 24 hours of data
            timestamp = now - timedelta(hours=i)
            for slice_obj in slices:
                metric = Metric(
                    timestamp=timestamp,
                    throughput=random.uniform(100, 1000),
                    latency=random.uniform(1.0, 50.0),
                    packet_loss=random.uniform(0, 5),
                    cpu_usage=random.uniform(10, 90),
                    memory_usage=random.uniform(20, 95),
                    slice_id=slice_obj.id,
                    device_id=random.choice(devices).id if devices else None
                )
                session.add(metric)
        
        # Create slice KPIs
        logger.info("Creating sample slice KPIs...")
        for slice_obj in slices:
            for i in range(24):  # Last 24 hours
                kpi = SliceKPI(
                    timestamp=now - timedelta(hours=i),
                    latency=random.uniform(1.0, 50.0),
                    throughput=random.uniform(100, 1000),
                    connected_devices=random.randint(10, 5000),
                    packet_loss=random.uniform(0, 5),
                    availability=random.uniform(95, 100),
                    slice_id=slice_obj.id
                )
                session.add(kpi)
        
        # Create sample alerts
        logger.info("Creating sample alerts...")
        alert_types = ["slice_created", "slice_modified", "device_connect", "alert_triggered", "config_updated"]
        alert_levels = ["info", "warning", "error"]
        
        for i in range(20):  # 20 sample alerts
            alert_time = now - timedelta(hours=random.randint(1, 24))
            alert_type = random.choice(alert_types)
            level = random.choice(alert_levels)
            slice_obj = random.choice(slices)
            
            if alert_type == "slice_created":
                message = f"New slice {slice_obj.name} was created"
            elif alert_type == "slice_modified":
                message = f"Configuration updated for slice {slice_obj.name}"
            elif alert_type == "device_connect":
                message = f"New device connected to slice {slice_obj.name}"
            elif alert_type == "alert_triggered":
                message = f"High latency detected on slice {slice_obj.name}"
            else:
                message = "System configuration updated"
            
            alert = Alert(
                timestamp=alert_time,
                level=level,
                message=message,
                resolved=random.choice([True, False]),
                resolved_at=alert_time + timedelta(minutes=random.randint(5, 60)) if random.choice([True, False]) else None,
                entity_type="slice",
                entity_id=slice_obj.id,
                context={"severity": level}
            )
            session.add(alert)
        
        await session.commit()
        logger.info("Sample data creation completed successfully")

async def main():
    """Main function to initialize the database and create sample data."""
    try:
        logger.info("Starting database initialization...")
        await create_sample_data()
        logger.info("Database initialization completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"Error creating sample data: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    import asyncio
    import sys
    
    # Configure logging to console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Run the main function
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
