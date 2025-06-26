# 5G Network Slice Manager

A comprehensive web-based dashboard for managing and monitoring 5G network slices with real-time analytics and alerting.

## 🌟 Features

- **Dashboard Overview**: Real-time visualization of network slice performance
- **Slice Management**: Create, update, and manage 5G network slices (eMBB, URLLC, mMTC, V2X, IoT)
- **Device Monitoring**: Track connected devices and their status
- **Performance Analytics**: Historical and real-time metrics visualization
- **Alert System**: Configurable alerts for network events and thresholds
- **User Management**: Role-based access control (RBAC)
- **API-First**: RESTful API for integration with other systems

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 13+ (with asyncpg support)
- Git

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/5g-slice-manager.git
   cd 5g-slice-manager
   ```

2. **Set up a virtual environment**
   ```bash
   # On Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and settings
   ```

5. **Initialize the database**
   ```bash
   python run_db_init.py
   ```

6. **Start the development server**
   ```bash
   python run.py
   ```

7. **Access the dashboard**
   - Open your browser to: http://localhost:8000
   - Login with default admin credentials:
     - **Username:** admin
     - **Password:** admin123

## 🛠 Development

### Project Structure

```
5g-slice-manager/
├── app/                    # Application package
│   ├── api/                # API routes
│   ├── core/               # Core functionality
│   ├── db/                 # Database models and migrations
│   ├── services/           # Business logic
│   └── static/             # Static files
├── scripts/                # Utility scripts
├── tests/                  # Test suite
├── .env.example            # Example environment variables
├── pyproject.toml          # Project configuration
├── requirements.txt        # Production dependencies
└── requirements-dev.txt    # Development dependencies
```

### Development Workflow

1. **Install development dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Run tests**
   ```bash
   pytest
   ```

3. **Format code**
   ```bash
   black .
   isort .
   ```

4. **Run with auto-reload**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/5gslice` | Database connection string |
| `SECRET_KEY` | `your-secret-key` | Secret key for session encryption |
| `DEBUG` | `True` | Debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SQL_ECHO` | `False` | Log SQL queries |

## 📚 API Documentation

API documentation is available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Database powered by [PostgreSQL](https://www.postgresql.org/) and [SQLAlchemy](https://www.sqlalchemy.org/)
- Frontend built with [Vue.js](https://vuejs.org/) and [Tailwind CSS](https://tailwindcss.com/)

## ⚙️ Local Development Setup (Recommended)

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- SQLite3
- Git (for version control)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd 5g-slicing
   ```

2. **Create and activate a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root:
   ```env
   # Database configuration (choose one)
   # For Neon PostgreSQL (recommended):
   NEON_DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require
   
   # For local PostgreSQL:
   # DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/5g_slicing
   
   # For SQLite (development only):
   # DATABASE_URL=sqlite+aiosqlite:///./slicing.db
   
   # Application settings
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ```

5. **Initialize the database**
   ```bash
   python -m scripts.init_db
   ```

## 🏃‍♂️ Running the Application Locally

### Development Mode

1. **Start the development server**
   ```bash
   # Using the built-in script (recommended)
   python main.py --reload --log-level debug
   
   # Or directly with uvicorn
   # uvicorn main:app --reload --port 8000 --log-level debug
   ```

2. **Access the application**
   - Dashboard: http://localhost:8000/dash/
   - API Documentation: http://localhost:8000/api/docs
   - WebSocket endpoint: ws://localhost:8000/ws/{client_id}

### Testing the WebSocket Connection

1. **Using the test script**
   ```bash
   python scripts/test_websocket.py
   ```

2. **Testing database connection**
   ```bash
   python scripts/test_db.py
   ```

## 🌐 WebSocket API

The application provides a WebSocket endpoint for real-time updates. Clients can connect to `ws://localhost:8000/ws/{client_id}` and subscribe to different channels.

### Available Channels
- `dashboard` - General dashboard updates
- `slices` - Network slice updates
- `metrics` - Performance metrics updates
- `alerts` - System alerts and notifications

### Message Format

**Client to Server:**
```json
{
  "action": "subscribe|unsubscribe|ping",
  "channels": ["channel1", "channel2"]
}
```

**Server to Client:**
```json
{
  "event_type": "event_name",
  "data": {},
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## 📊 Database Schema

The application uses the following main tables:
- `slices` - Network slice configurations
- `devices` - Connected devices
- `metrics` - Performance metrics
- `alerts` - System alerts
- `slice_kpis` - Key performance indicators for slices

## 🔒 Security Considerations

- All database connections use SSL/TLS when connecting to Neon PostgreSQL
- WebSocket connections are secured with WSS when using HTTPS
- Sensitive configuration is stored in environment variables
- Rate limiting is implemented for API endpoints
   - WebSocket Test: ws://localhost:8050/ws

### Running Tests
```bash
pytest tests/
```

## 🐳 Docker Setup (Alternative)

If you prefer using Docker, follow these steps:

1. **Build the Docker image**
   ```bash
   docker build -t 5g-slicing .
   ```

2. **Run the container**
   ```bash
   docker run -d --name 5g-slicing -p 8050:8050 5g-slicing
   ```

3. **Access the application**
   - Dashboard: http://localhost:8050/
   - API Docs: http://localhost:8050/docs

### Docker Compose (for development with hot-reload)

1. **Start the services**
   ```bash
   docker-compose up --build
   ```

2. **Access the application**
   - Dashboard: http://localhost:8050/
   - API Docs: http://localhost:8050/docs

### Production Mode

For production, use a production ASGI server like Uvicorn with Gunicorn:

```bash
pip install gunicorn
uvicorn main:app --host 0.0.0.0 --port 8050 --workers 4
```

## 🌐 WebSocket Endpoints

- `ws://localhost:8050/ws/{client_id}` - Connect to the WebSocket server
- `POST /api/broadcast` - Broadcast a message to all connected clients

## 🏗️ Project Structure

```
5g-slicing/
├── app/                    # Main application package
│   ├── dashboard/          # Dash application
│   ├── db/                 # Database models and migrations
│   └── websocket/          # WebSocket manager and handlers
├── config/                 # Configuration files
│   └── settings.py         # Application settings
├── data/                   # Database files
├── logs/                   # Log files
├── tests/                  # Test files
├── .env                    # Environment variables
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Access the Applications
- **API Documentation**: http://localhost:8000/api/docs
- **Dashboard**: http://localhost:8050
- **ReDoc Documentation**: http://localhost:8000/api/redoc

## NS-3 Integration

For detailed instructions on integrating with NS-3, see the [NS-3 Integration Guide](NS3-INTEGRATION.md).

## API Endpoints

### Slices
- `GET /api/slices/` - List all slices
- `POST /api/slices/` - Create a new slice
- `GET /api/slices/{slice_id}` - Get slice details
- `PUT /api/slices/{slice_id}` - Update a slice
- `DELETE /api/slices/{slice_id}` - Delete a slice

### NS-3 Integration
- `GET /api/ns3/slices/{slice_id}/config` - Get slice configuration for NS-3
- `POST /api/ns3/slices/{slice_id}/resources` - Update slice resources from NS-3
- `GET /api/ns3/slices/{slice_id}/kpis` - Get historical KPIs for a slice
- `WS /ws/kpi` - WebSocket for real-time KPI updates

### Metrics
- `GET /api/slices/{slice_id}/kpis` - Get slice KPIs
- `POST /api/slices/{slice_id}/kpis` - Add KPI data

## Dashboard Features

- **Real-time Monitoring**
  - Live KPI visualization
  - Resource utilization dashboards
  - SLA compliance tracking

- **Network Slicing**
  - Slice creation and configuration
  - Resource allocation management
  - Performance analytics

- **Alerting**
  - Real-time SLA violation alerts
  - Custom alert thresholds
  - Notification system

- **NS-3 Integration**
  - Simulation control panel
  - Real-time KPI visualization
  - Network topology viewer

## Project Structure

```
5g-slicing/
├── src/
│   ├── api/                 # API endpoints and routes
│   │   └── routers/         # API route definitions
│   ├── models/              # Database models and schemas
│   ├── services/            # Business logic and services
│   │   └── ns3/             # NS-3 integration
│   ├── static/              # Static files for dashboard
│   ├── websocket_manager.py # WebSocket management
│   └── main.py              # FastAPI application
├── scripts/
│   ├── test_ns3_client.py  # NS-3 test client
│   ├── simulate_ns3.py      # NS-3 data simulator
│   └── seed_db.py           # Database seeding
├── tests/                   # Test suite
├── config/                  # Configuration files
├── data/                    # Database files
├── requirements.txt         # Main requirements
├── requirements-dash.txt    # Dashboard requirements
├── run.py                   # Run FastAPI app
├── run_dashboard.py         # Run dashboard
└── NS3-INTEGRATION.md       # NS-3 integration guide
```

## Development

### Setting Up Development Environment

1. **Install development dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Run tests**
   ```bash
   pytest
   ```

3. **Code formatting**
   ```bash
   black .
   flake8
   ```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## Roadmap

### Upcoming Features
- [ ] Advanced NS-3 simulation control
- [ ] Multi-user support with authentication
- [ ] Advanced analytics and reporting
- [ ] Support for additional RAN types
- [ ] Containerization with Docker
- [ ] Kubernetes deployment

### Known Issues
- [ ] Check the [issues page](https://github.com/your-org/5g-slicing/issues) for known issues and feature requests

## Support

For support, please open an issue in the GitHub repository or contact me @ ireuben03@gmail.com.