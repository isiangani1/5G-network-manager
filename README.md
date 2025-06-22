# 5G Network Slice Manager

A comprehensive dashboard for managing and monitoring 5G network slices, built with FastAPI and Dash.


## Features

- Real-time monitoring of 5G network slices
- Interactive dashboards with live metrics
- KPI visualization (throughput, latency, connected devices)
- Network slice management interface
- System status monitoring
- Responsive design for desktop and mobile

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Setup and Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd 5g-slice-manager
   ```

2. **Create and activate a virtual environment** (recommended)
   - Windows:
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. **Start the server**
   ```bash
   uvicorn main:app --reload --port 8050
   ```

2. **Access the application**
   - Dashboard: http://127.0.0.1:8050/dashboard
   - API Documentation: http://127.0.0.1:8050/docs

## Development

### Adding New Dependencies
1. Install the new package:
   ```bash
   pip install package-name
   ```
2. Update requirements.txt:
   ```bash
   pip freeze > requirements.txt
   ```

### Running Tests
```bash
# Add test commands here when tests are implemented
pytest
```

---

*Built with ❤️ for 5G Network Management*
*by Siangani Ian Reuben*
