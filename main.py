from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from modules.common.interceptors import ResponseInterceptor
from modules.common.middlewares import (
    HttpErrorHandler,
    GenericErrorHandler,
    ValidationExceptionHandler,
)
from router import api_router
from utils.container import container
from utils.db_connection import SessionLocal

def create_app() -> FastAPI:
    app = FastAPI()

    # Override db_factory with the real session factory
    container.db_factory.override(SessionLocal)

    # Attach container to app (optional)
    app.container = container

    # Middlewares
    app.add_middleware(ResponseInterceptor)

    # Exception handlers
    app.add_exception_handler(HTTPException, HttpErrorHandler)
    app.add_exception_handler(RequestValidationError, ValidationExceptionHandler)
    app.add_exception_handler(Exception, GenericErrorHandler)

    # Routers
    app.include_router(api_router)

    return app


app = create_app()
