from sqlalchemy import text


class HealthService:
    """Liveness and readiness checks.

    Liveness answers "is the process up"; readiness answers "can it serve
    traffic", which for this app means the database is reachable.
    """

    def __init__(self, db_factory):
        self.db_factory = db_factory

    async def check_database(self) -> bool:
        try:
            async with self.db_factory() as db:
                await db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
