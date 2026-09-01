"""End-to-end user CRUD and the /users/me guard."""
# --- protected route --------------------------------------------------------

def test_me_returns_the_token_owner(client, register):
    _, token = register("alice")

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "alice"


def test_me_requires_a_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["message"] == "Token not found"


def test_me_rejects_an_invalid_token(client):
    response = client.get("/users/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid Token"


def test_me_sends_www_authenticate(client):
    assert client.get("/users/me").headers["www-authenticate"] == "Bearer"


# --- CRUD (all routes require a token) -------------------------------------

def test_crud_routes_require_authentication(client):
    assert client.get("/users/").status_code == 401
    assert client.post("/users/", json={"username": "bob", "password": "pw"}).status_code == 401
    assert client.get("/users/1").status_code == 401
    assert client.put("/users/1", json={"username": "x"}).status_code == 401
    assert client.delete("/users/1").status_code == 401


def test_list_users_returns_the_registered_user(client, register, auth_headers):
    listed = client.get("/users/", headers=auth_headers).json()["data"]
    assert [u["username"] for u in listed] == ["alice"]


def test_create_user_returns_201(client, auth_headers):
    created = client.post(
        "/users/", json={"username": "bob", "password": "pw"}, headers=auth_headers
    )
    assert created.status_code == 201
    assert created.json()["data"]["username"] == "bob"


def test_create_user_hashes_the_password(client, auth_headers, loop):
    from sqlalchemy import text

    from utils.db_connection import engine

    client.post(
        "/users/", json={"username": "bob", "password": "pw"}, headers=auth_headers
    )

    async def stored_password():
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT password FROM users WHERE username = 'bob'")
            )
            return result.scalar()

    hashed = loop.run_until_complete(stored_password())
    assert hashed != "pw"
    assert hashed.startswith("$2b$")


def test_a_user_created_via_crud_can_log_in(client, auth_headers):
    client.post(
        "/users/", json={"username": "bob", "password": "pw123456"}, headers=auth_headers
    )

    login = client.post("/auth/login", json={"username": "bob", "password": "pw123456"})
    assert login.status_code == 200


def test_responses_never_expose_the_password(client, register, auth_headers):
    listed = client.get("/users/", headers=auth_headers).json()["data"]
    assert all("password" not in user for user in listed)

    user_id = listed[0]["id"]
    assert "password" not in client.get(f"/users/{user_id}", headers=auth_headers).json()["data"]


def test_get_user_by_id(client, register, auth_headers):
    user_id = client.get("/users/", headers=auth_headers).json()["data"][0]["id"]

    response = client.get(f"/users/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "alice"


def test_update_user_applies_a_partial_change(client, register, auth_headers):
    user_id = client.get("/users/", headers=auth_headers).json()["data"][0]["id"]

    response = client.put(
        f"/users/{user_id}", json={"username": "alice2"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "alice2"


def test_update_with_an_empty_body_is_rejected(client, register, auth_headers):
    user_id = client.get("/users/", headers=auth_headers).json()["data"][0]["id"]

    response = client.put(f"/users/{user_id}", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["message"] == "No fields to update"


def test_delete_user_removes_it(client, register, auth_headers):
    user_id = client.get("/users/", headers=auth_headers).json()["data"][0]["id"]

    assert client.delete(f"/users/{user_id}", headers=auth_headers).status_code == 200
    assert client.get("/users/", headers=auth_headers).json()["data"] == []


def test_invalid_user_id_is_a_validation_error(client, auth_headers):
    assert client.get("/users/not-an-int", headers=auth_headers).status_code == 422


def test_create_user_requires_a_password(client, auth_headers):
    response = client.post("/users/", json={"username": "bob"}, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["errors"] == ["password: Field required"]


# --- previously known bugs, now fixed --------------------------------------

def test_duplicate_username_is_a_409_not_a_500(client, register, auth_headers):
    response = client.post(
        "/users/", json={"username": "alice", "password": "pw"}, headers=auth_headers
    )
    assert response.status_code == 409
    assert response.json()["message"] == "User with this user name already exists"


def test_duplicate_username_does_not_leak_database_internals(client, register, auth_headers):
    message = client.post(
        "/users/", json={"username": "alice", "password": "pw"}, headers=auth_headers
    ).json()["message"]
    assert "sqlalchemy" not in message.lower()
    assert "constraint" not in message.lower()


def test_missing_user_is_404(client, auth_headers):
    response = client.get("/users/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


def test_updating_a_missing_user_is_404(client, auth_headers):
    response = client.put(
        "/users/999999", json={"username": "x"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_deleting_a_missing_user_is_404(client, auth_headers):
    assert client.delete("/users/999999", headers=auth_headers).status_code == 404
