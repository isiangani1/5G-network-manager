import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# The API endpoint for fetching raw KPI data from the simulator
NS3_API_URL = os.getenv("NS3_API_URL", "http://localhost:8000/api/kpi")
