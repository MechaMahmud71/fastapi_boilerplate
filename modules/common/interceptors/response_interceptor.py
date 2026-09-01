import json

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from utils.response import envelope, error_envelope

SKIP_PREFIXES = ("/openapi", "/docs", "/redoc")


class ResponseInterceptor(BaseHTTPMiddleware):
    """Normalise every JSON response to the standard envelope.

    Success -> {success, data, message}
    Error   -> {success, data, errors, message}
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)

        if request.url.path.startswith(SKIP_PREFIXES):
            return response

        if "application/json" not in response.headers.get("content-type", ""):
            return response

        raw_body = b"".join([section async for section in response.body_iterator])
        if not raw_body:
            return response

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            data = raw_body.decode(errors="replace")

        success = response.status_code < 400
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "content-type")
        }

        if isinstance(data, dict):
            # Already an envelope (built by an error handler) -> keep as-is.
            if "success" in data and isinstance(data["success"], bool):
                body = (
                    envelope(data.get("data"), data.get("message"))
                    if data["success"]
                    else error_envelope(
                        data.get("message") or "Error",
                        errors=data.get("errors"),
                        data=data.get("data"),
                    )
                )
                return JSONResponse(
                    content=body, status_code=response.status_code, headers=headers
                )

            # FastAPI's own errors ({"detail": ...}) on a 4xx/5xx.
            if not success and "detail" in data:
                detail = data["detail"]
                if isinstance(detail, str):
                    return JSONResponse(
                        content=error_envelope(detail),
                        status_code=response.status_code,
                        headers=headers,
                    )
                return JSONResponse(
                    content=error_envelope("Error", data=detail),
                    status_code=response.status_code,
                    headers=headers,
                )

        if not success:
            return JSONResponse(
                content=error_envelope("Error", data=data),
                status_code=response.status_code,
                headers=headers,
            )

        return JSONResponse(
            content=envelope(data), status_code=response.status_code, headers=headers
        )
