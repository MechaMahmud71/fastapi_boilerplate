#!/usr/bin/env sh
# Container entrypoint: wait for the database, apply migrations, then exec the
# server. `exec` matters — it makes uvicorn PID 1 so it receives SIGTERM and
# shuts down gracefully.
set -e

echo "Waiting for the database..."
python - <<'PY'
import asyncio, os, sys, time
from sqlalchemy import text
from src.utils.db_connection import engine

async def wait(timeout=60):
    deadline = time.time() + timeout
    while True:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            print("Database is up.")
            return
        except Exception as exc:
            if time.time() > deadline:
                print(f"Database unreachable after {timeout}s: {exc}", file=sys.stderr)
                sys.exit(1)
            time.sleep(1)

asyncio.run(wait())
PY

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Applying migrations..."
  alembic upgrade head
fi

echo "Starting: $*"
exec "$@"
