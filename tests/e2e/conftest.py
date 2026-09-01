"""End-to-end fixtures: the real app, the real database.

Skipped automatically when PostgreSQL is not reachable, so the unit suite still
runs on a machine with no database.
"""
import asyncio

import pytest
from sqlalchemy import text

import main  # noqa: F401  (also resolves the modules/utils circular import)
from utils.db_connection import engine


@pytest.fixture(scope="session")
def loop():
    """One event loop for the whole session.

    The async engine's connection pool is bound to the loop that created it, so
    every request and every cleanup query must run on the same loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def require_database(loop):
    async def ping():
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        loop.run_until_complete(ping())
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database unavailable: {exc}", allow_module_level=True)


@pytest.fixture(scope="session")
def client(loop):
    from tests.asgi_client import ASGIClient

    return ASGIClient(main.app, loop=loop)


@pytest.fixture(autouse=True)
def clean_users(loop, require_database):
    """Start and finish every test with an empty users table."""

    async def truncate():
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users"))

    loop.run_until_complete(truncate())
    yield
    loop.run_until_complete(truncate())


@pytest.fixture
def register(client):
    """Register a user and return (payload, token)."""

    def _register(username="alice", password="secret123"):
        response = client.post(
            "/auth/register", json={"username": username, "password": password}
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        return data, data["accessToken"]

    return _register


@pytest.fixture
def auth_headers(register):
    _, token = register()
    return {"Authorization": f"Bearer {token}"}
