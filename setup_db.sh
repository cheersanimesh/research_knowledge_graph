#!/bin/bash
# Setup script for database initialization

set -e

echo "Setting up Paper Graph Knowledge System database..."

# Check if database URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is not set"
    echo "Please set it in your .env file or export it"
    exit 1
fi

# Extract database name from URL (simple extraction)
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

if [ -z "$DB_NAME" ]; then
    echo "Error: Could not extract database name from DATABASE_URL"
    exit 1
fi

echo "Database name: $DB_NAME"

# Run schema SQL
echo "Running schema migration..."
psql "$DATABASE_URL" -f sql/schema.sql

echo "Database setup complete!"
echo ""
echo "You can now run:"
echo "  python src/main.py ingest src/examples/sample_papers.json"

