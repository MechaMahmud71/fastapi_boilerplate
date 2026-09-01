"""End-to-end auth flows against the real app and database."""
import jwt

from src.modules.common.services.config_service import config_service


def test_register_creates_a_user_and_returns_a_token(client):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] is None
    assert set(body["data"]) == {"user", "accessToken"}
    assert body["data"]["user"]["username"] == "alice"


def test_register_response_never_includes_the_password(client):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret123"}
    )
    assert set(response.json()["data"]["user"]) == {"id", "username"}


def test_registered_password_is_hashed_in_the_database(client, loop):
    from sqlalchemy import text

    from src.utils.db_connection import engine

    client.post("/auth/register", json={"username": "alice", "password": "secret123"})

    async def stored_password():
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT password FROM users WHERE username = 'alice'")
            )
            return result.scalar()

    hashed = loop.run_until_complete(stored_password())
    assert hashed != "secret123"
    assert hashed.startswith("$2b$")


def test_register_token_is_valid_and_carries_claims(client):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret123"}
    )
    token = response.json()["data"]["accessToken"]

    claims = jwt.decode(
        token,
        config_service.get("JWT_SECRET"),
        algorithms=[config_service.get("JWT_ALGORITHM")],
    )
    assert claims["username"] == "alice"
    assert isinstance(claims["id"], int)


def test_duplicate_registration_is_rejected(client, register):
    register("alice")

    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 429
    assert response.json()["message"] == "User with this user name already exists"


def test_register_validates_username_length(client):
    response = client.post("/auth/register", json={"username": "ab", "password": "x"})

    assert response.status_code == 422
    assert response.json()["errors"] == [
        "username: String should have at least 3 characters"
    ]


def test_login_succeeds_with_correct_credentials(client, register):
    register("alice", "secret123")

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["username"] == "alice"


def test_login_rejects_unknown_user(client):
    response = client.post(
        "/auth/login", json={"username": "ghost", "password": "secret123"}
    )
    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


def test_login_rejects_wrong_password(client, register):
    register("alice", "secret123")

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Password does not match"


def test_register_then_login_returns_the_same_user(client, register):
    created, _ = register("alice", "secret123")

    login = client.post(
        "/auth/login", json={"username": "alice", "password": "secret123"}
    ).json()
    assert login["data"]["user"]["id"] == created["user"]["id"]
