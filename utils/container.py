from dependency_injector import containers, providers
from sqlalchemy.orm import sessionmaker, Session

from modules.user import UserRepository, UserService, UserController
from utils.db_connection import SessionLocal  # your SQLAlchemy session factory


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["modules.user", "modules.auth"]
    )

    # Provide the session factory (sessionmaker)
    db_factory = providers.Object(SessionLocal)

    # Repository
    user_repository = providers.Factory(
        UserRepository,
        db_factory=db_factory,  # inject the factory, not a session
    )

    # Service
    user_service = providers.Factory(
        UserService,
        user_repo=user_repository,
    )

    # Controller
    user_controller = providers.Factory(
        UserController,
        user_service=user_service,
    )


# Instantiate container
container = Container()
