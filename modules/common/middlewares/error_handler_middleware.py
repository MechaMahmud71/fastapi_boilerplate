from typing import List
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder

async def HttpErrorHandler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail, "data": None}
    )

async def GenericErrorHandler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": str(exc)or "Internal Server Error", "data": None}
    )


async def ValidationExceptionHandler(request: Request, exc: RequestValidationError):
    # Extract error messages
    errors:List[str] = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err.get("loc", []) if l != "body"])
        msg = err.get("msg", "")
        if loc:
            errors.append(f"{loc}: {msg}")
        else:
            errors.append(msg)

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "success": False,
            "messages": errors,
            "data":None
        })
    )
