import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.models import create_tables

def main():
    print("Creating database tables...")
    create_tables()
    print("Database tables created successfully!")

if __name__ == "__main__":
    main()
