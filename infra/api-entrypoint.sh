#!/bin/sh
set -e

cd /workspace/apps/api

echo "Running migrations..."
alembic upgrade head

echo "Seeding database (idempotent - no-op if already seeded)..."
python /workspace/scripts/seed_db.py

if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
