import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from router import api_router
from src.modules.common.interceptors.response_interceptor import ResponseInterceptor
from src.modules.common.middlewares.error_handler_middleware import GenericErrorHandler
from src.modules.common.middlewares.error_handler_middleware import HttpErrorHandler
from src.modules.common.middlewares.error_handler_middleware import (
    ValidationExceptionHandler,
)
from src.modules.common.services.config_service import config_service
from src.utils.container import container
from src.utils.db_connection import AsyncSessionLocal, engine

logging.basicConfig(
    level=config_service.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic: `alembic upgrade head`
    logger.info("Starting up in %s mode", config_service.env)
    yield
    await engine.dispose()
    logger.info("Shut down cleanly")


def create_app() -> FastAPI:
    # Interactive docs are on by default, and off in production unless
    # ENABLE_DOCS is set — they describe every route and schema you expose.
    docs_enabled = config_service.get_bool(
        "ENABLE_DOCS", default=not config_service.is_production
    )

    app = FastAPI(
        title=config_service.get("APP_NAME", "FastAPI Boilerplate"),
        version=config_service.get("APP_VERSION", "0.1.0"),
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # Override db_factory with async session factory
    container.db_factory.override(AsyncSessionLocal)

    # Attach container to app (optional)
    app.container = container

    # CORS. Defaults to "*" in development; set CORS_ORIGINS in production to
    # the exact origins your frontend is served from.
    origins = config_service.get_list(
        "CORS_ORIGINS", default=[] if config_service.is_production else ["*"]
    )
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=config_service.get_bool("CORS_ALLOW_CREDENTIALS", True),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Middlewares
    app.add_middleware(ResponseInterceptor)

    # Exception handlers
    # Starlette's base class covers router-raised 404/405 as well as
    # FastAPI's own HTTPException subclass.
    app.add_exception_handler(StarletteHTTPException, HttpErrorHandler)
    app.add_exception_handler(HTTPException, HttpErrorHandler)
    app.add_exception_handler(Exception, GenericErrorHandler)
    app.add_exception_handler(RequestValidationError, ValidationExceptionHandler)

    # Routers
    app.include_router(api_router)

    return app


app = create_app()
