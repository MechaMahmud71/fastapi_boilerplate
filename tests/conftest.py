"""Shared fixtures.

`import main` first: modules.* and utils.* have a circular import that only
resolves when the app package is imported as a whole.
"""
import main  # noqa: F401  isort:skip

import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import jwt
import pytest


def pytest_pyfunc_call(pyfuncitem):
    """Run `async def` tests without pytest-asyncio (not installable here).

    Each coroutine test gets its own event loop, which is fine for unit tests.
    The e2e suite overrides this with a session-wide loop, because the app's
    async DB engine is bound to the loop that created its connections.
    """
    test = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test):
        return None

    if getattr(pyfuncitem, "_shared_loop", None) is not None:
        loop = pyfuncitem._shared_loop
    else:
        loop = None

    kwargs = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
        if name in pyfuncitem.funcargs
    }

    if loop is not None:
        loop.run_until_complete(test(**kwargs))
    else:
        asyncio.run(test(**kwargs))
    return True

from src.modules.common.services import config_service


def make_token(claims: dict = None, expires_in_minutes: int = 60) -> str:
    """Sign a JWT the app will accept (or reject, for negative cases)."""
    payload = {"username": "tester", "id": 1}
    payload.update(claims or {})
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    return jwt.encode(
        payload,
        config_service.get("JWT_SECRET"),
        algorithm=config_service.get("JWT_ALGORITHM"),
    )


@pytest.fixture
def token() -> str:
    return make_token()


@pytest.fixture
def admin_token() -> str:
    return make_token({"role": "admin"})


@pytest.fixture
def expired_token() -> str:
    return make_token(expires_in_minutes=-5)


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}
