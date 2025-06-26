import asyncio
import websockets
import json
import random
from datetime import datetime, timedelta
import time

# WebSocket server details
WS_URI = "ws://localhost:8000/ws/kpi_updates"

async def simulate_ns3_data():
    """Simulate data from NS-3 and send via WebSocket"""
    slice_types = ["embb", "urllc", "mmtc"]
    slices = []
    
    # Generate some initial slices
    for i in range(1, 4):
        slice_type = slice_types[i-1]
        slices.append({
            "slice_id": f"{slice_type}_slice_{i}",
            "name": f"{slice_type.upper()} Slice {i}",
            "type": slice_type
        })
    
    async with websockets.connect(WS_URI) as websocket:
        print("Connected to WebSocket server")
        
        while True:
            try:
                for slice_data in slices:
                    # Generate random KPIs based on slice type
                    if slice_data["type"] == "embb":
                        latency = random.uniform(10.0, 50.0)
                        jitter = random.uniform(0.5, 5.0)
                        throughput = random.uniform(50.0, 200.0)
                        packet_loss = random.uniform(0.0001, 0.01)
                    elif slice_data["type"] == "urllc":
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
                    
                    # Create KPI message
                    message = {
                        "event": "kpi_update",
                        "slice_id": slice_data["slice_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "latency_ms": round(latency, 2),
                            "jitter_ms": round(jitter, 2),
                            "throughput_mbps": round(throughput, 2),
                            "packet_loss_rate": round(packet_loss, 6),
                            "sla_breach": random.random() < 0.1  # 10% chance of SLA breach
                        }
                    }
                    
                    # Send message
                    await websocket.send(json.dumps(message))
                    print(f"Sent KPI update for {slice_data['slice_id']}")
                    
                    # Small delay between slice updates
                    await asyncio.sleep(0.5)
                
                # Wait before next batch of updates
                await asyncio.sleep(5)
                
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed, reconnecting...")
                await asyncio.sleep(5)
                continue
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(simulate_ns3_data())
