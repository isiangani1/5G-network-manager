#!/bin/bash

# Database Backup Script
# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f "../../.env" ]; then
    export $(grep -v '^#' ../../.env | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found. Using default values.${NC}"
fi

# Default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-slicing_manager}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
BACKUP_DIR="../../backups/db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/backup_${DB_NAME}_${TIMESTAMP}.sql"
KEEP_DAYS=7  # Number of days to keep backups

# Function to display usage information
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --host HOST          Database host (default: localhost)"
    echo "  --port PORT          Database port (default: 5432)"
    echo "  --dbname NAME        Database name (default: slicing_manager)"
    echo "  --username USER      Database user (default: postgres)"
    echo "  --password PASSWORD  Database password (default: postgres)"
    echo "  --output DIR         Output directory for backups (default: ../../backups/db)"
    echo "  --keep-days DAYS     Number of days to keep backups (default: 7)"
    echo "  -h, --help           Show this help message"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            DB_HOST="$2"
            shift 2
            ;;
        --port)
            DB_PORT="$2"
            shift 2
            ;;
        --dbname)
            DB_NAME="$2"
            shift 2
            ;;
        --username)
            DB_USER="$2"
            shift 2
            ;;
        --password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --output)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --keep-days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if pg_dump is available
if ! command -v pg_dump &> /dev/null; then
    echo -e "${RED}Error: pg_dump command not found. Please install PostgreSQL client tools.${NC}"
    exit 1
fi

# Create backup
echo -e "${BLUE}Creating database backup...${NC}"
echo -e "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo -e "Backup file: ${BACKUP_FILE}"

# Set PGPASSWORD environment variable for non-interactive password input
export PGPASSWORD="$DB_PASSWORD"

# Run pg_dump to create the backup
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c -f "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    # Get backup file size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Backup created successfully (${BACKUP_SIZE})${NC}"
    
    # Clean up old backups
    echo -e "${BLUE}Cleaning up backups older than ${KEEP_DAYS} days...${NC}"
    find "$BACKUP_DIR" -name "backup_${DB_NAME}_*.sql" -type f -mtime +$((KEEP_DAYS-1)) -delete -print | while read -r file; do
        echo -e "${YELLOW}  Removed old backup: $(basename "$file")${NC}"
    done
    
    echo -e "${GREEN}✓ Backup and cleanup completed successfully${NC}"
else
    echo -e "${RED}✗ Backup failed${NC}"
    # Remove the failed backup file if it was created
    if [ -f "$BACKUP_FILE" ]; then
        rm -f "$BACKUP_FILE"
    fi
    exit 1
fi

# Unset the password
unset PGPASSWORD

exit 0