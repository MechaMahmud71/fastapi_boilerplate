from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
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
    # ✅ Run before the app starts
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables initialized")

    yield  # app runs here

    # ✅ Run after the app stops (optional cleanup)
    await engine.dispose()
    print("✅ Engine disposed")


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
