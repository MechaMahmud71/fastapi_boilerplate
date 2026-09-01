"""HealthService: readiness must degrade gracefully, never raise."""
import pytest

from src.modules.health.health_service import HealthService


class FakeSession:
    def __init__(self, error=None):
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement):
        if self.error:
            raise self.error
        return None


def factory_returning(session):
    return lambda: session


async def test_check_database_true_when_reachable():
    service = HealthService(factory_returning(FakeSession()))
    assert await service.check_database() is True


async def test_check_database_false_when_query_fails():
    service = HealthService(factory_returning(FakeSession(error=OSError("refused"))))
    assert await service.check_database() is False


async def test_check_database_swallows_any_exception():
    """A readiness probe must answer, not blow up with a 500."""
    service = HealthService(factory_returning(FakeSession(error=RuntimeError("boom"))))
    assert await service.check_database() is False
