from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
import json

class ResponseInterceptor(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)

        # Skip OpenAPI/docs routes
        if request.url.path.startswith("/openapi") or request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return response

        if "application/json" in response.headers.get("content-type", ""):
            body = [section async for section in response.body_iterator]
            raw_body = b"".join(body).decode()

            try:
                data = json.loads(raw_body)
            except:
                data = raw_body

            # Do not wrap errors again
            if isinstance(data, dict) and data.get("success") is False:
                return JSONResponse(content=data, status_code=response.status_code)

            # Wrap successful responses
            message = "Request successful"
            if isinstance(data, dict) and "message" in data:
                message = data.pop("message")

            return JSONResponse(
                content={
                    "success": True,
                    "message": message,
                    "data": data["data"] if "data" in data else data
                },
                status_code=response.status_code
            )

        return response



