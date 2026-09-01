"""Tests for the guard / metadata / param-decorator factories and the
auth decorators built on them."""
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from modules.common.decorators import CurrentUser, Protected, RoleGuard, Roles
from modules.common.interceptors import ResponseInterceptor
from modules.common.middlewares import (
    GenericErrorHandler,
    HttpErrorHandler,
    ValidationExceptionHandler,
)
from utils.decorators import ExecutionContext, create_guard, create_param_decorator

from tests.asgi_client import ASGIClient
from tests.conftest import make_token


class Body(BaseModel):
    title: str


def build_app() -> FastAPI:
    """A throwaway app wired exactly like main.py, with routes exercising
    every decorator feature."""
    app = FastAPI()
    app.add_middleware(ResponseInterceptor)
    app.add_exception_handler(HTTPException, HttpErrorHandler)
    app.add_exception_handler(Exception, GenericErrorHandler)
    app.add_exception_handler(RequestValidationError, ValidationExceptionHandler)

    @app.get("/me")
    @Protected
    async def me(user: dict = CurrentUser):
        return user

    @app.get("/state")
    @Protected
    async def state(request: Request):
        # legacy access path: the guard still populates request.state.user
        return request.state.user

    @app.post("/items/{item_id}")
    @Protected
    async def create_item(item_id: int, body: Body, user: dict = CurrentUser):
        return {"item_id": item_id, "title": body.title, "by": user["username"]}

    @app.get("/search")
    @Protected
    async def search(limit: int = 10):
        # no `request` parameter at all
        return {"limit": limit}

    @app.get("/admin")
    @Protected
    @RoleGuard
    @Roles("admin")
    async def admin_only(user: dict = CurrentUser):
        return {"role": user.get("role")}

    @app.get("/any")
    @Protected
    @RoleGuard
    async def any_user(user: dict = CurrentUser):
        # RoleGuard with no @Roles metadata -> nothing to enforce
        return {"user": user["username"]}

    @app.get("/unguarded")
    async def unguarded(user: dict = CurrentUser):
        return {"user": user}

    return app


@pytest.fixture
def client():
    return ASGIClient(build_app())


# --- @Protected: authentication --------------------------------------------

def test_valid_token_is_accepted(client, auth):
    r = client.get("/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "tester"


def test_missing_token_is_401(client):
    r = client.get("/me")
    assert r.status_code == 401
    assert r.json()["message"] == "Token not found"


def test_missing_token_sends_www_authenticate(client):
    r = client.get("/me")
    assert r.headers["www-authenticate"] == "Bearer"


def test_malformed_authorization_header_is_401(client, token):
    r = client.get("/me", headers={"Authorization": token})  # no "Bearer "
    assert r.status_code == 401
    assert r.json()["message"] == "Token not found"


def test_invalid_token_is_401(client):
    r = client.get("/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert r.json()["message"] == "Invalid Token"


def test_expired_token_is_401(client, expired_token):
    r = client.get("/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401
    assert r.json()["message"] == "Token Expired"


def test_token_signed_with_wrong_secret_is_rejected(client):
    import jwt as pyjwt

    bad = pyjwt.encode({"username": "mallory", "id": 99}, "not-the-secret", algorithm="HS256")
    r = client.get("/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_errors_use_the_standard_envelope(client):
    body = client.get("/me").json()
    assert list(body) == ["success", "data", "errors", "message"]
    assert body["success"] is False
    assert body["errors"] == ["Token not found"]


# --- the argument-passing bug that used to 500 -----------------------------

def test_guard_on_route_with_path_and_body_params(client, auth):
    r = client.post("/items/42", json={"title": "hello"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["data"] == {"item_id": 42, "title": "hello", "by": "tester"}


def test_guard_on_route_without_request_param(client, auth):
    r = client.get("/search?limit=5", headers=auth)
    assert r.status_code == 200
    assert r.json()["data"] == {"limit": 5}


def test_validation_still_runs_on_guarded_routes(client, auth):
    r = client.post("/items/abc", json={"title": "x"}, headers=auth)
    assert r.status_code == 422


def test_guard_runs_before_validation_of_body(client):
    # unauthenticated + invalid body -> auth failure wins
    r = client.post("/items/1", json={})
    assert r.status_code == 401


# --- CurrentUser: param decorator ------------------------------------------

def test_current_user_is_injected(client, auth):
    assert client.get("/me", headers=auth).json()["data"]["id"] == 1


def test_request_state_user_still_populated(client, auth):
    assert client.get("/state", headers=auth).json()["data"]["username"] == "tester"


def test_current_user_is_none_without_a_guard(client):
    r = client.get("/unguarded")
    assert r.status_code == 200
    assert r.json()["data"]["user"] is None


# --- RoleGuard + @Roles: stacked guards and metadata -----------------------

def test_admin_route_allows_matching_role(client, admin_token):
    r = client.get("/admin", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["data"]["role"] == "admin"


def test_admin_route_rejects_wrong_role(client, auth):
    r = client.get("/admin", headers=auth)
    assert r.status_code == 403
    assert r.json()["message"] == "Insufficient permissions"


def test_admin_route_rejects_missing_token_before_role_check(client):
    r = client.get("/admin")
    assert r.status_code == 401  # authn failure, not 403


def test_role_guard_without_metadata_allows_everyone(client, auth):
    assert client.get("/any", headers=auth).status_code == 200


def test_stacked_guards_share_one_context(client, admin_token):
    # RoleGuard reads the user published by Protected rather than re-decoding
    r = client.get("/admin", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["data"]["role"] == "admin"


# --- create_guard / create_param_decorator: the factories ------------------

def test_custom_guard_allows_and_rejects():
    def api_key_guard(ctx: ExecutionContext) -> bool:
        return ctx.request.headers.get("X-API-Key") == "let-me-in"

    ApiKey = create_guard(api_key_guard, message="Bad API key", status_code=403)

    app = FastAPI()
    app.add_exception_handler(HTTPException, HttpErrorHandler)

    @app.get("/keyed")
    @ApiKey
    async def keyed():
        return {"ok": True}

    c = ASGIClient(app)
    assert c.get("/keyed", headers={"X-API-Key": "let-me-in"}).status_code == 200
    bad = c.get("/keyed", headers={"X-API-Key": "nope"})
    assert bad.status_code == 403
    assert bad.json()["message"] == "Bad API key"


def test_async_guard_is_awaited():
    async def async_guard(ctx: ExecutionContext) -> bool:
        return ctx.request.headers.get("X-Ok") == "1"

    Gate = create_guard(async_guard, status_code=403)
    app = FastAPI()
    app.add_exception_handler(HTTPException, HttpErrorHandler)

    @app.get("/gate")
    @Gate
    async def gate():
        return {"ok": True}

    c = ASGIClient(app)
    assert c.get("/gate", headers={"X-Ok": "1"}).status_code == 200
    assert c.get("/gate").status_code == 403


def test_guard_provides_value_to_param_decorator():
    Tenant = create_guard(
        lambda ctx: ctx.request.headers.get("X-Tenant", "public"), provides="tenant"
    )
    CurrentTenant = create_param_decorator(lambda ctx: ctx.get("tenant"))

    app = FastAPI()

    @app.get("/t")
    @Tenant
    async def t(tenant: str = CurrentTenant):
        return {"tenant": tenant}

    c = ASGIClient(app)
    assert c.get("/t", headers={"X-Tenant": "acme"}).json() == {"tenant": "acme"}


def test_custom_param_decorator_without_guard():
    UserAgent = create_param_decorator(lambda ctx: ctx.request.headers.get("user-agent"))
    app = FastAPI()

    @app.get("/ua")
    async def ua(agent: str = UserAgent):
        return {"agent": agent}

    assert ASGIClient(app).get("/ua", headers={"User-Agent": "pytest"}).json() == {
        "agent": "pytest"
    }


def test_security_scheme_is_declared_in_openapi(client):
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]


def test_guard_params_are_hidden_from_openapi(client):
    schema = client.get("/openapi.json").json()
    params = schema["paths"]["/items/{item_id}"]["post"].get("parameters", [])
    assert [p["name"] for p in params] == ["item_id"]


def test_unguarded_route_has_no_security(client):
    schema = client.get("/openapi.json").json()
    assert "security" not in schema["paths"]["/unguarded"]["get"]
