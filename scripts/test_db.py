"""
Test script for database connection and initialization.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test the database connection and initialization."""
    from app.db.database import init_db, async_session_factory as AsyncSessionLocal
    
    try:
        logger.info("Testing database connection...")
        
        # Test connection
        async with AsyncSessionLocal() as session:
            result = await session.execute("SELECT 1")
            logger.info(f"Connection test successful: {result.scalar() == 1}")
        
        # Test initialization
        logger.info("Initializing database...")
        success = await init_db()
        
        if success:
            logger.info("Database initialization successful")
            
            # List all tables
            async with AsyncSessionLocal() as session:
                if os.getenv('DB_TYPE', 'sqlite') in ('postgres', 'postgresql'):
                    result = await session.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                else:  # SQLite
                    result = await session.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    """)
                
                tables = [row[0] for row in result.fetchall()]
                logger.info(f"Found {len(tables)} tables: {', '.join(tables) if tables else 'None'}")
                
        return True
        
    except Exception as e:
        logger.error(f"Database test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Load environment variables if .env exists
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run the test
    success = asyncio.run(test_database_connection())
    
    if not success:
        logger.error("Database test failed")
        sys.exit(1)
    
    logger.info("Database test completed successfully")
