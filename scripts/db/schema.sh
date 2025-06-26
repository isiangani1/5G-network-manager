#!/bin/bash

# Database Schema Management Script
# This script manages database schema versions and migrations

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
MIGRATIONS_DIR="./migrations"
SCHEMA_VERSION_TABLE="schema_version"

# Function to display usage information
show_help() {
    echo "Usage: $0 [command] [options]"
    echo "Commands:"
    echo "  init                  Initialize the database with the base schema"
    echo "  migrate [version]     Apply all pending migrations or up to the specified version"
    echo "  rollback [version]    Roll back the most recent migration or to the specified version"
    echo "  status               Show current schema version and pending migrations"
    echo "  create [name]        Create a new migration file"
    echo ""
    echo "Options:"
    echo "  --host HOST          Database host (default: localhost)"
    echo "  --port PORT          Database port (default: 5432)"
    echo "  --dbname NAME        Database name (default: slicing_manager)"
    echo "  --username USER      Database user (default: postgres)"
    echo "  --password PASSWORD  Database password (default: postgres)"
    echo "  --migrations-dir DIR Directory containing migrations (default: ./migrations)"
    echo "  -h, --help           Show this help message"
    exit 0
}

# Function to run a SQL query and return the result
run_query() {
    local query="$1"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "$query" 2>/dev/null
}

# Function to initialize the database
initialize_database() {
    echo -e "${BLUE}Initializing database...${NC}"
    
    # Check if the database exists
    if ! run_query "SELECT 1" &>/dev/null; then
        echo -e "${YELLOW}Database ${DB_NAME} does not exist. Creating...${NC}"
        PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to create database ${DB_NAME}${NC}"
            return 1
        fi
    fi
    
    # Create schema version table if it doesn't exist
    local version_table_exists=$(run_query "SELECT to_regclass('${SCHEMA_VERSION_TABLE}')::text")
    if [ -z "$version_table_exists" ]; then
        echo -e "${BLUE}Creating schema version table...${NC}"
        run_query "
            CREATE TABLE ${SCHEMA_VERSION_TABLE} (
                version INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )"
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to create schema version table${NC}"
            return 1
        fi
        
        # Insert initial version
        run_query "INSERT INTO ${SCHEMA_VERSION_TABLE} (version, name) VALUES (0, 'initial')"
        echo -e "${GREEN}✓ Database initialized with version 0${NC}"
    else
        echo -e "${YELLOW}Database already initialized${NC}"
    fi
    
    return 0
}

# Function to get current schema version
get_current_version() {
    local version=$(run_query "SELECT MAX(version) FROM ${SCHEMA_VERSION_TABLE}" 2>/dev/null)
    if [ -z "$version" ]; then
        echo -1
    else
        echo $version
    fi
}

# Function to get all migrations
# Migrations should be named like: V{number}__{description}.sql
# Example: V1__create_users_table.sql
# Returns a list of version numbers and names
list_migrations() {
    local migrations=()
    
    # Find all migration files and sort them by version number
    while IFS= read -r file; do
        local filename=$(basename "$file")
        if [[ $filename =~ ^V([0-9]+)__(.+\.sql)$ ]]; then
            local version=${BASH_REMATCH[1]}
            local name=${BASH_REMATCH[2]%.sql}
            migrations+=("$version|$name")
        fi
    done < <(find "$MIGRATIONS_DIR" -name "V*__*.sql" | sort -V)
    
    # Sort by version number
    IFS=$'\n' sorted=($(sort -t'|' -k1,1n <<<"${migrations[*]}"))
    unset IFS
    
    for migration in "${sorted[@]}"; do
        echo "$migration"
    done
}

# Function to apply a migration
apply_migration() {
    local version=$1
    local name=$2
    local file="$MIGRATIONS_DIR/V${version}__${name}.sql"
    
    if [ ! -f "$file" ]; then
        echo -e "${RED}Migration file not found: $file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Applying migration: V${version}__${name}${NC}"
    
    # Start a transaction
    echo "BEGIN;" > /tmp/migration_apply.sql
    
    # Add the migration SQL
    cat "$file" >> /tmp/migration_apply.sql
    
    # Update the schema version
    echo "INSERT INTO ${SCHEMA_VERSION_TABLE} (version, name) VALUES (${version}, '${name}');" >> /tmp/migration_apply.sql
    
    # Commit the transaction
    echo "COMMIT;" >> /tmp/migration_apply.sql
    
    # Execute the migration
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f /tmp/migration_apply.sql
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Applied migration V${version}__${name}${NC}"
        rm -f /tmp/migration_apply.sql
        return 0
    else
        echo -e "${RED}✗ Failed to apply migration V${version}__${name}${NC}"
        rm -f /tmp/migration_apply.sql
        return 1
    fi
}

# Function to rollback a migration
rollback_migration() {
    local version=$1
    local name=$2
    local file="$MIGRATIONS_DIR/V${version}__${name}.sql"
    
    # Check if there's a corresponding rollback file
    local rollback_file="${file%.sql}.rollback.sql"
    
    if [ ! -f "$rollback_file" ]; then
        echo -e "${YELLOW}No rollback file found for V${version}__${name}${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Rolling back migration: V${version}__${name}${NC}"
    
    # Start a transaction
    echo "BEGIN;" > /tmp/migration_rollback.sql
    
    # Add the rollback SQL
    cat "$rollback_file" >> /tmp/migration_rollback.sql
    
    # Update the schema version
    echo "DELETE FROM ${SCHEMA_VERSION_TABLE} WHERE version = ${version};" >> /tmp/migration_rollback.sql
    
    # Commit the transaction
    echo "COMMIT;" >> /tmp/migration_rollback.sql
    
    # Execute the rollback
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f /tmp/migration_rollback.sql
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Rolled back migration V${version}__${name}${NC}"
        rm -f /tmp/migration_rollback.sql
        return 0
    else
        echo -e "${RED}✗ Failed to roll back migration V${version}__${name}${NC}"
        rm -f /tmp/migration_rollback.sql
        return 1
    fi
}

# Function to show migration status
show_status() {
    local current_version=$(get_current_version)
    echo -e "${BLUE}Current schema version: ${current_version}${NC}"
    echo ""
    
    echo -e "${BLUE}Migrations:${NC}"
    echo "--------------------------------------------------"
    printf "%8s  %-30s  %-10s\n" "Version" "Name" "Status"
    echo "--------------------------------------------------"
    
    local applied_versions=($(run_query "SELECT version FROM ${SCHEMA_VERSION_TABLE} ORDER BY version" 2>/dev/null))
    
    while IFS='|' read -r version name; do
        local status="${RED}PENDING${NC}"
        
        # Check if this version is in the applied_versions array
        for applied_version in "${applied_versions[@]}"; do
            if [ "$applied_version" = "$version" ]; then
                status="${GREEN}APPLIED${NC}"
                break
            fi
        done
        
        printf "%8s  %-30s  %b\n" "$version" "$name" "$status"
    done < <(list_migrations)
    
    echo "--------------------------------------------------"
}

# Function to create a new migration
create_migration() {
    local name=$1
    if [ -z "$name" ]; then
        echo -e "${RED}Migration name is required${NC}"
        echo "Usage: $0 create <migration_name>"
        exit 1
    fi
    
    # Create migrations directory if it doesn't exist
    mkdir -p "$MIGRATIONS_DIR"
    
    # Get the next version number
    local next_version=1
    local last_migration=$(list_migrations | tail -n 1)
    
    if [ -n "$last_migration" ]; then
        IFS='|' read -r last_version _ <<< "$last_migration"
        next_version=$((last_version + 1))
    fi
    
    # Create migration files
    local migration_file="${MIGRATIONS_DIR}/V${next_version}__${name}.sql"
    local rollback_file="${MIGRATIONS_DIR}/V${next_version}__${name}.rollback.sql"
    
    # Create migration file
    cat > "$migration_file" << EOF
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
    
    # Create rollback file
    cat > "$rollback_file" << EOF
-- Rollback migration: $name
-- Created at: $(date)

-- Add your SQL for rolling back the migration here

-- Example (reverse of the above):
-- DROP TABLE IF EXISTS table_name;

EOF
    
    echo -e "${GREEN}✓ Created migration: V${next_version}__${name}${NC}"
    echo "  Migration:   $migration_file"
    echo "  Rollback:    $rollback_file"
}

# Main script execution
main() {
    # Parse command line arguments
    local command=$1
    shift
    
    # Parse options
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
            --migrations-dir)
                MIGRATIONS_DIR="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                ;;
            -*)
                echo "Unknown option: $1"
                show_help
                ;;
            *)
                # This is the command argument
                break
                ;;
        esac
    done
    
    # Execute the command
    case "$command" in
        init)
            initialize_database
            ;;
        migrate)
            local target_version=$1
            migrate "$target_version"
            ;;
        rollback)
            local target_version=$1
            rollback "$target_version"
            ;;
        status)
            show_status
            ;;
        create)
            create_migration "$1"
            ;;
        *)
            echo -e "${RED}Unknown command: $command${NC}"
            show_help
            ;;
    esac
}

# Function to migrate to a specific version
migrate() {
    local target_version=$1
    local current_version=$(get_current_version)
    
    # If database is not initialized, initialize it
    if [ "$current_version" -eq -1 ]; then
        initialize_database
        current_version=0
    fi
    
    # Get all migrations
    local migrations=()
    while IFS= read -r line; do
        migrations+=("$line")
    done < <(list_migrations)
    
    # Apply pending migrations
    local applied=0
    for migration in "${migrations[@]}"; do
        IFS='|' read -r version name <<< "$migration"
        
        # Skip already applied migrations
        if [ "$version" -le "$current_version" ]; then
            continue
        fi
        
        # If target version is specified, stop when we reach it
        if [ -n "$target_version" ] && [ "$version" -gt "$target_version" ]; then
            break
        fi
        
        # Apply the migration
        if ! apply_migration "$version" "$name"; then
            echo -e "${RED}Migration failed at version $version${NC}"
            return 1
        fi
        
        applied=$((applied + 1))
    done
    
    if [ "$applied" -eq 0 ]; then
        echo -e "${YELLOW}No migrations to apply${NC}"
    else
        echo -e "${GREEN}✓ Applied $applied migration(s)${NC}"
    fi
}

# Function to rollback to a specific version
rollback() {
    local target_version=$1
    local current_version=$(get_current_version)
    
    if [ "$current_version" -eq -1 ]; then
        echo -e "${YELLOW}Database is not initialized${NC}"
        return 0
    fi
    
    # If no target version specified, roll back one migration
    if [ -z "$target_version" ]; then
        # Get the most recent applied migration
        local last_migration=$(run_query "SELECT version, name FROM ${SCHEMA_VERSION_TABLE} WHERE version = (SELECT MAX(version) FROM ${SCHEMA_VERSION_TABLE})" 2>/dev/null)
        if [ -z "$last_migration" ]; then
            echo -e "${YELLOW}No migrations to roll back${NC}"
            return 0
        fi
        
        IFS='|' read -r version name <<< "$last_migration"
        target_version=$((version - 1))
    fi
    
    # Get all applied migrations in reverse order
    local applied_migrations=()
    while IFS='|' read -r version name; do
        applied_migrations+=("$version|$name")
    done < <(run_query "SELECT version, name FROM ${SCHEMA_VERSION_TABLE} WHERE version > ${target_version} ORDER BY version DESC" 2>/dev/null)
    
    if [ ${#applied_migrations[@]} -eq 0 ]; then
        echo -e "${YELLOW}No migrations to roll back${NC}"
        return 0
    fi
    
    # Roll back migrations
    local rolled_back=0
    for migration in "${applied_migrations[@]}"; do
        IFS='|' read -r version name <<< "$migration"
        
        if ! rollback_migration "$version" "$name"; then
            echo -e "${RED}Rollback failed at version $version${NC}"
            return 1
        fi
        
        rolled_back=$((rolled_back + 1))
    done
    
    echo -e "${GREEN}✓ Rolled back $rolled_back migration(s) to version ${target_version}${NC}"
}

# Run the main function
main "$@"
