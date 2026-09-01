from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.security import HTTPBearer
from src.utils.container import container
from src.utils.db_connection import AsyncSessionLocal, engine
from router import api_router
from src.modules.common.interceptors.response_interceptor import ResponseInterceptor
from src.modules.common.middlewares.error_handler_middleware import HttpErrorHandler
from src.modules.common.middlewares.error_handler_middleware import GenericErrorHandler
from src.modules.common.middlewares.error_handler_middleware import ValidationExceptionHandler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic: `alembic upgrade head`
    yield
    await engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    # Override db_factory with async session factory
    container.db_factory.override(AsyncSessionLocal)

    # Attach container to app (optional)
    app.container = container

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
