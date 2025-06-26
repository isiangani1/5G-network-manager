import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlalchemy.orm import Session
from src.models import Base, engine, Slice, SliceResource, SliceKPI
from datetime import datetime, timedelta
import random

def create_test_data(db: Session):
    """Create test data for the database"""
    
    # Clear existing data
    db.query(SliceKPI).delete()
    db.query(SliceResource).delete()
    db.query(Slice).delete()
    
    # Create test slices
    slices = [
        {
            "slice_id": "slice_embb_1",
            "name": "eMBB Video Streaming",
            "description": "Enhanced Mobile Broadband for video streaming",
            "priority": 1
        },
        {
            "slice_id": "slice_urllc_1",
            "name": "URLLC Industrial IoT",
            "description": "Ultra-Reliable Low-Latency Communications for industrial IoT",
            "priority": 1
        },
        {
            "slice_id": "slice_mmtc_1",
            "name": "mMTC Smart City",
            "description": "Massive Machine Type Communications for smart city applications",
            "priority": 3
        },
        {
            "slice_id": "slice_embb_2",
            "name": "eMBB General",
            "description": "General purpose enhanced Mobile Broadband",
            "priority": 2
        }
    ]
    
    # Add slices to database
    for slice_data in slices:
        db_slice = Slice(**slice_data)
        db.add(db_slice)
    
    db.commit()
    
    # Define resource types and units
    resource_types = [
        ("cpu", "cores"),
        ("memory", "GB"),
        ("bandwidth", "Mbps"),
        ("storage", "GB")
    ]
    
    # Add resources to each slice
    for slice_data in slices:
        slice_id = slice_data["slice_id"]
        
        # Different resource allocations based on slice type
        if "embb" in slice_id:
            cpu = random.randint(2, 8)
            memory = random.randint(4, 16)
            bandwidth = random.randint(100, 500)
            storage = random.randint(50, 200)
        elif "urllc" in slice_id:
            cpu = random.randint(1, 4)
            memory = random.randint(2, 8)
            bandwidth = random.randint(10, 100)
            storage = random.randint(10, 50)
        else:  # mmtc
            cpu = random.randint(1, 2)
            memory = random.randint(1, 4)
            bandwidth = random.randint(10, 50)
            storage = random.randint(5, 20)
        
        # Create resource entries
        resources = [
            {"resource_type": "cpu", "allocated": cpu, "max_limit": cpu * 2, "unit": "cores"},
            {"resource_type": "memory", "allocated": memory, "max_limit": memory * 2, "unit": "GB"},
            {"resource_type": "bandwidth", "allocated": bandwidth, "max_limit": bandwidth * 2, "unit": "Mbps"},
            {"resource_type": "storage", "allocated": storage, "max_limit": storage * 2, "unit": "GB"}
        ]
        
        for res in resources:
            db_resource = SliceResource(slice_id=slice_id, **res)
            db.add(db_resource)
    
    db.commit()
    
    # Generate KPI data for the last 7 days
    now = datetime.utcnow()
    for i in range(7):
        timestamp = now - timedelta(days=(6 - i))
        
        for slice_data in slices:
            slice_id = slice_data["slice_id"]
            
            # Generate realistic KPI values based on slice type
            if "embb" in slice_id:
                latency = random.uniform(10.0, 50.0)
                jitter = random.uniform(0.5, 5.0)
                throughput = random.uniform(50.0, 200.0)
                packet_loss = random.uniform(0.0001, 0.01)
            elif "urllc" in slice_id:
                latency = random.uniform(1.0, 10.0)
                jitter = random.uniform(0.1, 1.0)
                throughput = random.uniform(10.0, 50.0)
                packet_loss = random.uniform(0.00001, 0.001)
            else:  # mmtc
                latency = random.uniform(50.0, 200.0)
                jitter = random.uniform(5.0, 20.0)
                throughput = random.uniform(1.0, 10.0)
                packet_loss = random.uniform(0.1, 1.0)
            
            # Add some random variation
            latency += random.uniform(-5.0, 5.0)
            jitter = max(0.1, jitter + random.uniform(-1.0, 1.0))
            throughput = max(1.0, throughput + random.uniform(-10.0, 10.0))
            packet_loss = max(0.0, packet_loss + random.uniform(-0.01, 0.01))
            
            # Create KPI record
            kpi = SliceKPI(
                slice_id=slice_id,
                timestamp=timestamp,
                latency_ms=latency,
                jitter_ms=jitter,
                throughput_mbps=throughput,
                packet_loss_rate=packet_loss,
                sla_breach=random.random() < 0.1  # 10% chance of SLA breach
            )
            db.add(kpi)
    
    db.commit()

def main():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Seeding database with test data...")
    db = Session(engine)
    try:
        create_test_data(db)
        print("Database seeded successfully!")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
