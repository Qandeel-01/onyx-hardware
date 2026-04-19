#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
until PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "\q" 2>/dev/null; do
  echo "Waiting for PostgreSQL at $DB_HOST..."
  sleep 2
done

echo "PostgreSQL is ready!"

# Run migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start the application
echo "Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
