"""End-to-end todo CRUD, including per-user isolation and the cascade."""
from sqlalchemy import text

from src.utils.db_connection import engine


def create_todo(client, headers, **fields):
    payload = {"title": "buy milk"}
    payload.update(fields)
    response = client.post("/todos/", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- auth -------------------------------------------------------------------

def test_all_todo_routes_require_authentication(client):
    assert client.get("/todos/").status_code == 401
    assert client.post("/todos/", json={"title": "x"}).status_code == 401
    assert client.get("/todos/1").status_code == 401
    assert client.put("/todos/1", json={"title": "x"}).status_code == 401
    assert client.delete("/todos/1").status_code == 401


# --- create -----------------------------------------------------------------

def test_create_returns_201_and_the_todo(client, auth_headers):
    todo = create_todo(client, auth_headers, description="2L")

    assert todo["title"] == "buy milk"
    assert todo["description"] == "2L"
    assert todo["completed"] is False
    assert isinstance(todo["user_id"], int)


def test_create_assigns_the_authenticated_user(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()["data"]
    todo = create_todo(client, auth_headers)

    assert todo["user_id"] == me["id"]


def test_create_rejects_an_empty_title(client, auth_headers):
    response = client.post("/todos/", json={"title": ""}, headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["errors"] == [
        "title: String should have at least 1 character"
    ]


def test_create_requires_a_title(client, auth_headers):
    response = client.post("/todos/", json={}, headers=auth_headers)
    assert response.status_code == 422


# --- list -------------------------------------------------------------------

def test_list_is_empty_initially(client, auth_headers):
    body = client.get("/todos/", headers=auth_headers).json()["data"]
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_returns_created_todos(client, auth_headers):
    create_todo(client, auth_headers, title="one")
    create_todo(client, auth_headers, title="two")

    body = client.get("/todos/", headers=auth_headers).json()["data"]
    assert [t["title"] for t in body["items"]] == ["one", "two"]
    assert body["total"] == 2


def test_list_filters_by_completed(client, auth_headers):
    create_todo(client, auth_headers, title="open")
    create_todo(client, auth_headers, title="done", completed=True)

    done = client.get("/todos/?completed=true", headers=auth_headers).json()["data"]
    assert [t["title"] for t in done["items"]] == ["done"]

    open_ = client.get("/todos/?completed=false", headers=auth_headers).json()["data"]
    assert [t["title"] for t in open_["items"]] == ["open"]


def test_list_paginates(client, auth_headers):
    for title in ("a", "b", "c"):
        create_todo(client, auth_headers, title=title)

    page = client.get("/todos/?limit=2&offset=1", headers=auth_headers).json()["data"]
    assert [t["title"] for t in page["items"]] == ["b", "c"]
    assert page["total"] == 3  # total is the unpaginated count


def test_list_rejects_an_out_of_range_limit(client, auth_headers):
    assert client.get("/todos/?limit=0", headers=auth_headers).status_code == 422
    assert client.get("/todos/?limit=101", headers=auth_headers).status_code == 422


# --- read / update / delete -------------------------------------------------

def test_get_one(client, auth_headers):
    todo = create_todo(client, auth_headers)

    response = client.get(f"/todos/{todo['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "buy milk"


def test_get_missing_is_404(client, auth_headers):
    response = client.get("/todos/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Todo not found"


def test_update_applies_a_partial_change(client, auth_headers):
    todo = create_todo(client, auth_headers, description="2L")

    response = client.put(
        f"/todos/{todo['id']}", json={"completed": True}, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["completed"] is True
    assert data["title"] == "buy milk"       # untouched
    assert data["description"] == "2L"       # untouched


def test_update_with_an_empty_body_is_rejected(client, auth_headers):
    todo = create_todo(client, auth_headers)

    response = client.put(f"/todos/{todo['id']}", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["message"] == "No fields to update"


def test_update_missing_is_404(client, auth_headers):
    response = client.put("/todos/999999", json={"title": "x"}, headers=auth_headers)
    assert response.status_code == 404


def test_delete_removes_the_todo(client, auth_headers):
    todo = create_todo(client, auth_headers)

    assert client.delete(f"/todos/{todo['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"/todos/{todo['id']}", headers=auth_headers).status_code == 404


def test_delete_missing_is_404(client, auth_headers):
    assert client.delete("/todos/999999", headers=auth_headers).status_code == 404


# --- one-to-many isolation --------------------------------------------------

def test_todos_are_scoped_to_their_owner(client, auth_headers, other_headers):
    create_todo(client, auth_headers, title="alice's")
    create_todo(client, other_headers, title="bob's")

    alice = client.get("/todos/", headers=auth_headers).json()["data"]
    bob = client.get("/todos/", headers=other_headers).json()["data"]

    assert [t["title"] for t in alice["items"]] == ["alice's"]
    assert [t["title"] for t in bob["items"]] == ["bob's"]


def test_another_users_todo_is_404_not_403(client, auth_headers, other_headers):
    """403 would confirm the id exists; 404 reveals nothing."""
    todo = create_todo(client, auth_headers, title="private")

    response = client.get(f"/todos/{todo['id']}", headers=other_headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Todo not found"


def test_another_user_cannot_update_or_delete(client, auth_headers, other_headers):
    todo = create_todo(client, auth_headers, title="private")

    assert client.put(
        f"/todos/{todo['id']}", json={"title": "hijacked"}, headers=other_headers
    ).status_code == 404
    assert client.delete(f"/todos/{todo['id']}", headers=other_headers).status_code == 404

    # still intact for the owner
    assert client.get(f"/todos/{todo['id']}", headers=auth_headers).json()["data"]["title"] == "private"


def test_a_user_can_have_many_todos(client, auth_headers):
    for i in range(5):
        create_todo(client, auth_headers, title=f"todo {i}")

    body = client.get("/todos/", headers=auth_headers).json()["data"]
    assert body["total"] == 5
    assert len({t["id"] for t in body["items"]}) == 5


def test_deleting_a_user_cascades_to_their_todos(client, auth_headers, loop):
    me = client.get("/users/me", headers=auth_headers).json()["data"]
    create_todo(client, auth_headers)

    async def todo_count(user_id):
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT count(*) FROM todos WHERE user_id = :uid"),
                {"uid": user_id},
            )
            return result.scalar()

    assert loop.run_until_complete(todo_count(me["id"])) == 1

    assert client.delete(f"/users/{me['id']}", headers=auth_headers).status_code == 200
    assert loop.run_until_complete(todo_count(me["id"])) == 0
