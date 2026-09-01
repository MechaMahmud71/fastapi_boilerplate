"""A tiny synchronous ASGI test client.

Starlette's TestClient needs httpx, which is not installable in this
environment. This drives the app directly over the ASGI interface and exposes
the small slice of the requests/httpx API the tests use.
"""
import asyncio
import json as jsonlib
from typing import Any, Dict, Optional
from urllib.parse import urlsplit


class Response:
    def __init__(self, status_code: int, headers: Dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = body

    @property
    def text(self) -> str:
        return self.content.decode()

    def json(self) -> Any:
        return jsonlib.loads(self.content)


class ASGIClient:
    """Call an ASGI app in-process, one request at a time.

    Pass ``loop`` to run every request on one event loop — required when the
    app holds loop-bound resources such as an async DB engine/connection pool.
    Without it each request gets a fresh loop via ``asyncio.run``.
    """

    def __init__(self, app, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.app = app
        self.loop = loop

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Any = None,
    ) -> Response:
        coro = self._request(method, url, headers, json)
        if self.loop is not None:
            return self.loop.run_until_complete(coro)
        return asyncio.run(coro)

    def get(self, url, **kw) -> Response:
        return self.request("GET", url, **kw)

    def post(self, url, **kw) -> Response:
        return self.request("POST", url, **kw)

    def put(self, url, **kw) -> Response:
        return self.request("PUT", url, **kw)

    def delete(self, url, **kw) -> Response:
        return self.request("DELETE", url, **kw)

    async def _request(self, method, url, headers, json) -> Response:
        split = urlsplit(url)
        raw_headers = [(b"host", b"testserver")]
        for key, value in (headers or {}).items():
            raw_headers.append((key.lower().encode(), value.encode()))

        body = b""
        if json is not None:
            body = jsonlib.dumps(json).encode()
            raw_headers.append((b"content-type", b"application/json"))
            raw_headers.append((b"content-length", str(len(body)).encode()))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": split.path or "/",
            "raw_path": (split.path or "/").encode(),
            "query_string": split.query.encode(),
            "root_path": "",
            "headers": raw_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }

        request_sent = False

        async def receive():
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        status = {"code": 500}
        out_headers: Dict[str, str] = {}
        chunks = []
        response_started = False

        async def send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                status["code"] = message["status"]
                for key, value in message.get("headers", []):
                    out_headers[key.decode().lower()] = value.decode()
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        try:
            await self.app(scope, receive, send)
        except Exception:
            # Starlette's ServerErrorMiddleware sends the 500 response and then
            # re-raises so the server can log it. Uvicorn swallows that; do the
            # same here, but only once a response has actually been sent.
            if not response_started:
                raise

        return Response(status["code"], out_headers, b"".join(chunks))
