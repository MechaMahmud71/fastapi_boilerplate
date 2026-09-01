# src/modules/health/health_controller.py
from fastapi import APIRouter

from src.modules.health.health_service import HealthService
from src.utils.expection import HttpError


class HealthController:
    def __init__(self, health_service: HealthService):
        self.health_service = health_service
        self.router = APIRouter(tags=["Health"])
        self.__add_routes()

    def __add_routes(self):
        @self.router.get("/health")
        async def health():
            """Liveness: the process is running. Never touches the database."""
            return {"status": "ok"}

        @self.router.get("/health/ready")
        async def readiness():
            """Readiness: dependencies are reachable. Use this for load
            balancer checks — a 503 takes the instance out of rotation."""
            if not await self.health_service.check_database():
                raise HttpError("Database unavailable", 503)
            return {"status": "ready", "database": "ok"}
