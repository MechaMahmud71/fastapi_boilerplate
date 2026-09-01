"""The response envelope applied by ResponseInterceptor."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from src.modules.common.interceptors import ResponseInterceptor
from src.modules.common.middlewares import (
    GenericErrorHandler,
    HttpErrorHandler,
    ValidationExceptionHandler,
)
from tests.asgi_client import ASGIClient
from src.utils import HttpError


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(ResponseInterceptor)
    app.add_exception_handler(HTTPException, HttpErrorHandler)
    app.add_exception_handler(Exception, GenericErrorHandler)
    app.add_exception_handler(RequestValidationError, ValidationExceptionHandler)

    @app.get("/dict")
    async def as_dict():
        return {"id": 1}

    @app.get("/list")
    async def as_list():
        return [{"id": 1}, {"id": 2}]

    @app.get("/none")
    async def as_none():
        return None

    @app.get("/bool")
    async def as_bool():
        return False

    @app.get("/int")
    async def as_int():
        return 42

    @app.get("/string")
    async def as_string():
        return "plain"

    @app.get("/message-field")
    async def message_field():
        # a record whose own column is called "message"
        return {"id": 1, "message": "my own column"}

    @app.get("/data-field")
    async def data_field():
        # a record whose own column is called "data"
        return {"id": 1, "data": "payload", "other": "kept"}

    @app.get("/raises")
    async def raises():
        raise HttpError("nope", 418)

    return ASGIClient(app)


def test_success_envelope_shape(client):
    body = client.get("/dict").json()
    assert list(body) == ["success", "data", "message"]
    assert body == {"success": True, "data": {"id": 1}, "message": None}


def test_list_payload_is_untouched(client):
    assert client.get("/list").json()["data"] == [{"id": 1}, {"id": 2}]


@pytest.mark.parametrize(
    "path,expected",
    [("/none", None), ("/bool", False), ("/int", 42), ("/string", "plain")],
)
def test_non_dict_payloads_do_not_crash(client, path, expected):
    """These used to 500 with "argument of type 'X' is not iterable"."""
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["data"] == expected


def test_payload_message_field_is_not_stolen(client):
    data = client.get("/message-field").json()
    assert data["data"] == {"id": 1, "message": "my own column"}
    assert data["message"] is None


def test_payload_data_field_keeps_siblings(client):
    data = client.get("/data-field").json()["data"]
    assert data == {"id": 1, "data": "payload", "other": "kept"}


def test_error_envelope_shape(client):
    response = client.get("/raises")
    assert response.status_code == 418
    body = response.json()
    assert list(body) == ["success", "data", "errors", "message"]
    assert body == {
        "success": False,
        "data": None,
        "errors": ["nope"],
        "message": "nope",
    }


def test_framework_404_is_reported_as_failure(client):
    response = client.get("/no-such-route")
    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "errors": ["Not Found"],
        "message": "Not Found",
    }


def test_framework_405_is_reported_as_failure(client):
    response = client.post("/dict")
    assert response.status_code == 405
    assert response.json()["success"] is False


def test_errors_are_not_double_wrapped(client):
    body = client.get("/raises").json()
    assert body["data"] is None  # not a nested envelope
