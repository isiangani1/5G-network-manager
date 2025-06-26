import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL")
    print(f"Connecting to database...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url, sslmode='require')
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nFound {len(tables)} tables in the database:")
        
        for table in tables:
            print(f"\nTable: {table}")
            
            # Get row count
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            count = cursor.fetchone()[0]
            print(f"  Rows: {count}")
            
            # Get column info
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s;
            """, (table,))
            
            columns = cursor.fetchall()
            print("  Columns:")
            for col in columns:
                print(f"    - {col[0]}: {col[1]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
