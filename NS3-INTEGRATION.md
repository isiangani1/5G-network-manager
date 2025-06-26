# NS-3 Integration Guide

This document explains how to integrate the 5G Network Slicing Manager with NS-3 for network simulation and monitoring.

## Prerequisites

- Python 3.8+
- NS-3 (optional, for full integration)
- Redis (for WebSocket message broker, optional)
- InfluxDB (for time-series metrics, optional)

## Architecture

```
┌─────────────────┐     ┌───────────────────────┐     ┌─────────────────┐
│                 │     │                       │     │                 │
│    NS-3 Sim    │────▶│  5G Slicing Manager  │────▶│   Dashboard     │
│                 │     │   - API (FastAPI)     │     │   (Plotly Dash) │
└─────────────────┘     │   - WebSocket Server  │     │                 │
                        │   - NS-3 Collector    │     └─────────────────┘
                        └───────────┬───────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │                       │
                        │       Database        │
                        │       (SQLite)│
                        │                       │
                        └───────────────────────┘
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# For NS-3 integration (optional)
pip install ns3

# For monitoring (optional)
pip install influxdb-client prometheus-client
```

### 2. Configure Environment

Create a `.env` file with your configuration:

```env
# Database
DATABASE_URL=sqlite:///./slicing.db

# NS-3 Collector
NS3_COLLECTOR_HOST=0.0.0.0
NS3_COLLECTOR_PORT=9090

# WebSocket
WEBSOCKET_URL=ws://localhost:8000/ws/kpi

# InfluxDB (optional)
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=your-bucket
```

### 3. Initialize the Database

```bash
python -c "from src.models import init_db; init_db()"
```

## Running the Application

### 1. Start the API Server

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the NS-3 Collector (if not using the built-in one)

```bash
python -m src.services.ns3.collector
```

### 3. Run the Test NS-3 Client

```bash
python scripts/test_ns3_client.py --duration 300 --interval 1.0
```

## API Endpoints

### NS-3 Integration Endpoints

- `GET /api/ns3/slices/{slice_id}/config` - Get slice configuration
- `POST /api/ns3/slices/{slice_id}/resources` - Update slice resources
- `GET /api/ns3/slices/{slice_id}/kpis` - Get slice KPIs
- `WS /ws/kpi` - WebSocket for real-time KPI updates

### WebSocket Protocol

The WebSocket server broadcasts messages in the following format:

```json
{
  "event": "kpi_update",
  "data": {
    "slice_id": "slice_123",
    "timestamp": "2023-06-15T12:00:00Z",
    "metrics": {
      "latency_ms": 25.5,
      "jitter_ms": 1.2,
      "throughput_mbps": 150.0,
      "packet_loss_rate": 0.001,
      "sla_breach": false
    },
    "sla_violations": {
      "high_latency": {
        "metric": "latency_ms",
        "value": 125.5,
        "threshold": 100,
        "message": "Latency exceeds 100ms threshold"
      }
    }
  }
}
```

## NS-3 Integration

### Sending Data from NS-3

You can send data from an NS-3 simulation using either:

1. **UDP Socket** (recommended for C++ NS-3 scripts)
2. **HTTP API** (for Python-based NS-3 scripts)
3. **WebSocket Client** (for real-time updates)

#### Example: Sending KPIs from NS-3 (C++)

```cpp
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"
#include "ns3/network-application-helper.h"

using namespace ns3;

void SendKPI(double latency, double jitter, double throughput, double packetLoss) {
    // Create a socket
    Ptr<Socket> socket = Socket::CreateSocket(
        NodeList::GetNode(0),
        TypeId::LookupByName("ns3::UdpSocketFactory")
    );
    
    // Connect to the collector
    InetSocketAddress remote = InetSocketAddress("127.0.0.1", 9090);
    socket->Connect(remote);
    
    // Prepare the KPI data
    std::stringstream ss;
    ss << R"({"slice_id":"slice_123","metrics":{"latency_ms":)" 
       << latency << R"(,"jitter_ms":)" << jitter 
       << R"(,"throughput_mbps":)" << throughput 
       << R"(,"packet_loss_rate":)" << packetLoss << "}}";
    
    // Send the data
    Ptr<Packet> packet = Create<Packet>(
        (const uint8_t*)ss.str().c_str(),
        ss.str().length()
    );
    socket->Send(packet);
}
```

## Monitoring and Alerting

The system includes built-in support for:

1. **InfluxDB** - For time-series metrics storage
2. **Prometheus** - For metrics collection
3. **WebSocket Alerts** - For real-time notifications

To enable monitoring, configure the appropriate environment variables and ensure the services are running.

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Ensure the WebSocket server is running
   - Check CORS settings if connecting from a different origin
   - Verify the WebSocket URL is correct

2. **Database Connection Issues**
   - Check the database URL in your `.env` file
   - Ensure the database server is running
   - Verify database permissions

3. **NS-3 Integration Problems**
   - Check the NS-3 collector is running
   - Verify the port numbers match
   - Check firewall settings if running on different machines

## Next Steps

1. Implement authentication for the API and WebSocket endpoints
2. Add more sophisticated SLA violation detection
3. Integrate with Grafana for advanced visualization
4. Add support for distributed NS-3 simulations

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
