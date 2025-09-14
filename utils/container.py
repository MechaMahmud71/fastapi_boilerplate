# containers.py
from dependency_injector import containers, providers
from sqlalchemy.orm import Session

from repositories.user_repository import UserRepository
from services.user_service import UserService


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["modules.user", "modules.auth"]
    )

    # DB session provider (FastAPI will still manage sessions via get_db)
    db = providers.Dependency(instance_of=Session)

    # Repository
    user_repository = providers.Factory(
        UserRepository,
        db=db,
    )

    # Service
    user_service = providers.Factory(
        UserService,
        user_repo=user_repository,
    )
