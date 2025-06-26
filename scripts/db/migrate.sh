#!/bin/bash

# Database Migration Script
# This script handles database migrations for the 5G Slicing Manager

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f "../.env" ]; then
    export $(grep -v '^#' ../.env | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found. Using default values.${NC}"
fi

# Default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-slicing_manager}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
MIGRATIONS_DIR="./migrations"

# Parse command line arguments
COMMAND=""
VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        up|down|create|status)
            COMMAND="$1"
            shift
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
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
        -h|--help)
            echo "Usage: $0 [command] [options]"
            echo "Commands:"
            echo "  up        Apply all available migrations"
            echo "  down      Roll back the most recent migration"
            echo "  create    Create a new migration file"
            echo "  status    Show migration status"
            echo ""
            echo "Options:"
            echo "  -v, --version VERSION  Target migration version"
            echo "  --host HOST            Database host (default: localhost)"
            echo "  --port PORT            Database port (default: 5432)"
            echo "  --dbname NAME          Database name (default: slicing_manager)"
            echo "  --username USER        Database user (default: postgres)"
            echo "  --password PASSWORD    Database password (default: postgres)"
            echo "  -h, --help            Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if command is provided
if [ -z "$COMMAND" ]; then
    echo -e "${RED}Error: No command specified${NC}"
    echo "Use '$0 --help' for usage information"
    exit 1
fi

# Create migrations directory if it doesn't exist
mkdir -p "$MIGRATIONS_DIR"

# Function to run migrations
run_migrations() {
    local direction=$1
    local target=$2
    
    echo -e "${BLUE}Running ${direction} migrations...${NC}"
    
    # Use migra to generate SQL for the target database
    # This is a simplified example - in a real implementation, you would use a proper migration tool
    # like Flyway, Liquibase, or a language-specific ORM migration tool
    
    # For PostgreSQL, we'll use psql with migration files
    if [ "$direction" = "up" ]; then
        # Find all SQL files in the migrations directory and sort them
        find "$MIGRATIONS_DIR" -name "*.up.sql" | sort | while read -r file; do
            echo -e "${BLUE}Applying migration: $(basename "$file")${NC}"
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$file"
            if [ $? -ne 0 ]; then
                echo -e "${RED}Error applying migration: $(basename "$file")${NC}"
                exit 1
            fi
        done
    elif [ "$direction" = "down" ]; then
        # Find the most recent migration and run its down.sql file
        local latest_migration=$(find "$MIGRATIONS_DIR" -name "*.down.sql" | sort -r | head -n 1)
        if [ -n "$latest_migration" ]; then
            echo -e "${BLUE}Reverting migration: $(basename "$latest_migration")${NC}"
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$latest_migration"
            if [ $? -ne 0 ]; then
                echo -e "${RED}Error reverting migration: $(basename "$latest_migration")${NC}"
                exit 1
            fi
        else
            echo -e "${YELLOW}No migrations to revert${NC}"
        fi
    fi
    
    echo -e "${GREEN}✓ Migrations completed successfully${NC}"
}

# Function to create a new migration
create_migration() {
    local name=$1
    local timestamp=$(date +%Y%m%d%H%M%S)
    local migration_name="${timestamp}_${name}"
    local up_file="${MIGRATIONS_DIR}/${migration_name}.up.sql"
    local down_file="${MIGRATIONS_DIR}/${migration_name}.down.sql"
    
    # Create up migration
    cat > "$up_file" << EOF
-- Migration: $name
-- Created at: $(date)

-- Add your SQL for migrating UP here

-- Example:
-- CREATE TABLE IF NOT EXISTS table_name (
--     id SERIAL PRIMARY KEY,
--     name VARCHAR(255) NOT NULL,
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
-- );

EOF
    
    # Create down migration
    cat > "$down_file" << EOF
-- Rollback migration: $name
-- Created at: $(date)

-- Add your SQL for rolling back the migration here

-- Example:
-- DROP TABLE IF EXISTS table_name;

EOF
    
    echo -e "${GREEN}✓ Created migration: ${migration_name}${NC}"
    echo "  Up:   ${up_file}"
    echo "  Down: ${down_file}"
}

# Function to show migration status
show_status() {
    echo -e "${BLUE}=== Database Migration Status ===${NC}"
    echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
    echo "User: ${DB_USER}"
    echo ""
    
    # List all migration files
    echo -e "${BLUE}Available migrations:${NC}"
    find "$MIGRATIONS_DIR" -name "*.up.sql" | sort | while read -r file; do
        local migration_name=$(basename "$file" .up.sql)
        echo "- ${migration_name}"
    done
    
    # In a real implementation, you would query the database to see which migrations have been applied
    echo -e "\n${BLUE}Note: Migration status tracking not implemented in this example.${NC}"
    echo "In a real implementation, you would see which migrations have been applied."
}

# Execute the requested command
case "$COMMAND" in
    up)
        run_migrations "up" "$VERSION"
        ;;
    down)
        run_migrations "down" "$VERSION"
        ;;
    create)
        if [ -z "$VERSION" ]; then
            echo -e "${RED}Error: Migration name is required${NC}"
            echo "Usage: $0 create <migration_name>"
            exit 1
        fi
        create_migration "$VERSION"
        ;;
    status)
        show_status
        ;;
    *)
        echo -e "${RED}Error: Unknown command: $COMMAND${NC}"
        exit 1
        ;;
esac

exit 0
