#!/bin/bash

# Database Restore Script
# This script restores a 5G Slicing Manager database from a backup

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

# Function to display usage information
show_help() {
    echo "Usage: $0 [options] [backup_file]"
    echo "Options:"
    echo "  --host HOST          Database host (default: localhost)"
    echo "  --port PORT          Database port (default: 5432)"
    echo "  --dbname NAME        Database name to restore to (default: slicing_manager)"
    echo "  --username USER      Database user (default: postgres)"
    echo "  --password PASSWORD  Database password (default: postgres)"
    echo "  --input DIR          Directory containing backups (default: ../../backups/db)"
    echo "  --latest             Restore the most recent backup"
    echo "  --list               List available backups and exit"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "If backup_file is not provided and --latest is not specified, a list of available"
    echo "backups will be shown for selection."
    exit 0
}

# Parse command line arguments
LATEST=false
LIST_ONLY=false

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
        --input)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --latest)
            LATEST=true
            shift
            ;;
        --list)
            LIST_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        -*)
            echo "Unknown option: $1"
            show_help
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

# Function to list available backups
list_backups() {
    local backups=()
    local count=0
    
    echo -e "${BLUE}Available backups in ${BACKUP_DIR}:${NC}"
    
    # Find all backup files and sort by modification time (newest first)
    while IFS= read -r -d $'\0' file; do
        count=$((count + 1))
        file_date=$(stat -c "%y" "$file" | cut -d. -f1)
        file_size=$(du -h "$file" | cut -f1)
        backups+=("$file")
        printf "%3d) %-50s (%s, %s)\n" "$count" "$(basename "$file")" "$file_date" "$file_size"
    done < <(find "$BACKUP_DIR" -name "backup_${DB_NAME}_*.sql" -type f -print0 2>/dev/null | sort -zr)
    
    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}No backup files found in ${BACKUP_DIR}${NC}"
        return 1
    fi
    
    echo ""
    echo -n "Enter the number of the backup to restore (or 'q' to quit): "
    
    local choice
    read -r choice
    
    if [ "$choice" = "q" ] || [ -z "$choice" ]; then
        echo "Restore cancelled."
        return 1
    fi
    
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt $count ]; then
        echo -e "${RED}Invalid selection. Please enter a number between 1 and $count.${NC}"
        return 1
    fi
    
    BACKUP_FILE="${backups[$((choice-1))]}"
    return 0
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if psql and pg_restore are available
for cmd in psql pg_restore; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd command not found. Please install PostgreSQL client tools.${NC}"
        exit 1
    fi
done

# If no backup file specified and not using --latest, show list
if [ -z "$BACKUP_FILE" ] && [ "$LATEST" = false ]; then
    list_backups
    if [ $? -ne 0 ] && [ "$LIST_ONLY" = false ]; then
        exit 1
    fi
    if [ "$LIST_ONLY" = true ]; then
        exit 0
    fi
fi

# If --latest is specified, find the most recent backup
if [ "$LATEST" = true ]; then
    BACKUP_FILE=$(find "$BACKUP_DIR" -name "backup_${DB_NAME}_*.sql" -type f -print0 2>/dev/null | sort -zr | head -zn1 | tr '\0' '\n')
    if [ -z "$BACKUP_FILE" ]; then
        echo -e "${RED}No backup files found in ${BACKUP_DIR}${NC}"
        exit 1
    fi
    echo -e "${BLUE}Using latest backup: ${BACKUP_FILE}${NC}"
fi

# Verify backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: ${BACKUP_FILE}${NC}"
    exit 1
fi

# Confirm before proceeding
if [ "$LIST_ONLY" = false ]; then
    echo -e "${YELLOW}WARNING: This will overwrite the database ${DB_NAME} on ${DB_HOST}:${DB_PORT}${NC}"
    echo -e "Backup file: ${BACKUP_FILE}"
    echo -n "Are you sure you want to continue? (y/N): "
    read -r confirm
    
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Restore cancelled."
        exit 0
    fi
    
    # Set PGPASSWORD environment variable for non-interactive password input
    export PGPASSWORD="$DB_PASSWORD"
    
    # Drop and recreate the database
    echo -e "${BLUE}Recreating database...${NC}"
    
    # Terminate all connections to the database
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '${DB_NAME}'
        AND pid <> pg_backend_pid();"
    
    # Drop and recreate the database
    dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$DB_NAME"
    createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
    
    # Restore the database
    echo -e "${BLUE}Restoring database from backup...${NC}"
    
    # Check if the backup is in custom format (-F c) or plain SQL
    if file "$BACKUP_FILE" | grep -q "PostgreSQL custom database dump"; then
        pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" "$BACKUP_FILE"
    else
        # For plain SQL backups, use psql
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$BACKUP_FILE"
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Database restored successfully${NC}"
    else
        echo -e "${RED}✗ Database restore failed${NC}"
        # Unset the password before exiting
        unset PGPASSWORD
        exit 1
    fi
    
    # Unset the password
    unset PGPASSWORD
fi

exit 0
