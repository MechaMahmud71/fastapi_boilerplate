"""The three exception handlers registered in main.py."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from src.modules.common.middlewares import (
    GenericErrorHandler,
    HttpErrorHandler,
    ValidationExceptionHandler,
)
from tests.asgi_client import ASGIClient
from src.utils import HttpError


class Body(BaseModel):
    username: str
    password: str


@pytest.fixture
def client():
    app = FastAPI()
    app.add_exception_handler(HTTPException, HttpErrorHandler)
    app.add_exception_handler(Exception, GenericErrorHandler)
    app.add_exception_handler(RequestValidationError, ValidationExceptionHandler)

    @app.get("/http-error")
    async def http_error():
        raise HttpError("not allowed", 403)

    @app.get("/with-headers")
    async def with_headers():
        raise HttpError("unauthorised", 401, {"WWW-Authenticate": "Bearer"})

    @app.get("/boom")
    async def boom():
        raise ValueError("kaboom")

    @app.post("/validate")
    async def validate(body: Body):
        return body

    return ASGIClient(app)


def test_http_error_uses_its_own_status(client):
    response = client.get("/http-error")
    assert response.status_code == 403
    assert response.json()["message"] == "not allowed"


def test_http_error_forwards_headers(client):
    response = client.get("/with-headers")
    assert response.headers["www-authenticate"] == "Bearer"


def test_unhandled_exception_is_500(client):
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json()["success"] is False


def test_unhandled_exception_does_not_leak_internals(client):
    """str(exc) used to be returned verbatim, exposing driver/SQL details."""
    body = client.get("/boom").json()
    assert body["message"] == "Internal Server Error"
    assert "kaboom" not in body["message"]
    assert body["errors"] == ["Internal Server Error"]


def test_validation_lists_one_entry_per_field(client):
    response = client.post("/validate", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["errors"] == ["username: Field required", "password: Field required"]
    assert body["message"] == "username: Field required; password: Field required"
    assert body["data"] is None


def test_validation_reports_path_params(client):
    body = client.post("/validate", json={"username": 1, "password": "x"}).json()
    assert any("username" in error for error in body["errors"])


def test_all_error_bodies_share_one_shape(client):
    for path in ("/http-error", "/boom"):
        assert list(client.get(path).json()) == [
            "success",
            "data",
            "errors",
            "message",
        ]
    assert list(client.post("/validate", json={}).json()) == [
        "success",
        "data",
        "errors",
        "message",
    ]
