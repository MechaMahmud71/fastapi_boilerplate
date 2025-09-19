from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from utils.container import container
from utils.db_connection import AsyncSessionLocal, engine, Base
from router import api_router
from modules.common.interceptors import ResponseInterceptor
from modules.common.middlewares import (
    HttpErrorHandler,
    GenericErrorHandler,
    ValidationExceptionHandler,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    app.add_exception_handler(HTTPException, HttpErrorHandler)
    app.add_exception_handler(Exception, GenericErrorHandler)
    app.add_exception_handler(RequestValidationError, ValidationExceptionHandler)

    # Routers
    app.include_router(api_router)

    return app


app = create_app()
