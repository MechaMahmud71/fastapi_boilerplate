# utils/container.py
from dependency_injector import containers, providers
from src.modules.auth.auth_controller import AuthController
from src.modules.auth.auth_service import AuthService
from src.modules.todo.todo_controller import TodoController
from src.modules.todo.todo_repository import TodoRepository
from src.modules.todo.todo_service import TodoService
from src.modules.user.user_repository import UserRepository
from src.modules.user.user_service import UserService
from src.modules.user.user_controller import UserController
from src.utils.db_connection import AsyncSessionLocal  # ✅ use async session factory


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["src.modules.user", "src.modules.auth", "src.modules.todo"]
    )

    # Provide the async session factory (sessionmaker)
    db_factory = providers.Object(AsyncSessionLocal)

    # Repository
    user_repository = providers.Factory(
        UserRepository,
        db_factory=db_factory,  # inject async session factory
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

    # Todo
    todo_repository = providers.Factory(
        TodoRepository,
        db_factory=db_factory,
    )

    todo_service = providers.Factory(
        TodoService,
        todo_repo=todo_repository,
    )

    todo_controller = providers.Factory(
        TodoController,
        todo_service=todo_service,
    )

    auth_service= providers.Factory(
        AuthService,
        user_service=user_service
    )

    auth_controller=providers.Factory(
        AuthController,
        auth_service=auth_service
    )


# Instantiate container
container = Container()
