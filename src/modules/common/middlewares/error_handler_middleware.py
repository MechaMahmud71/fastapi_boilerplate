import logging
from typing import List

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from utils.response import error_envelope

logger = logging.getLogger(__name__)


async def HttpErrorHandler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def GenericErrorHandler(request: Request, exc: Exception):
    # Log the detail server-side; never leak internals (driver names, SQL,
    # constraint names) to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_envelope("Internal Server Error"),
    )


async def ValidationExceptionHandler(request: Request, exc: RequestValidationError):
    # One entry per invalid field, e.g. "password: Field required"
    errors: List[str] = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err.get("loc", []) if l != "body"])
        msg = err.get("msg", "")
        errors.append(f"{loc}: {msg}" if loc else msg)

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            error_envelope("; ".join(errors) or "Validation error", errors=errors)
        ),
    )
