"""TodoService rules, with a fake repository (no database).

The rule that matters most here is ownership: a todo belonging to someone else
must be indistinguishable from one that does not exist.
"""
import pytest

from src.modules.todo.dtos.create_dto import CreateTodoDTO
from src.modules.todo.dtos.update_dto import UpdateTodoDTO
from src.modules.todo.todo_model import Todo
from src.modules.todo.todo_service import TodoService
from src.utils.expection import HttpError

OWNER = 1
STRANGER = 2


class FakeTodoRepository:
    def __init__(self, todos=None):
        self.todos = {t.id: t for t in (todos or [])}
        self.calls = []
        self._next_id = max(self.todos, default=0) + 1

    async def create_todo(self, user_id: int, dto: CreateTodoDTO) -> Todo:
        self.calls.append(("create_todo", user_id, dto))
        todo = Todo(id=self._next_id, user_id=user_id, **dto.model_dump())
        self.todos[todo.id] = todo
        self._next_id += 1
        return todo

    async def get_todo_by_id(self, todo_id: int):
        self.calls.append(("get_todo_by_id", todo_id))
        return self.todos.get(todo_id)

    async def get_todos_by_user(self, user_id, completed=None, limit=50, offset=0):
        self.calls.append(("get_todos_by_user", user_id, completed, limit, offset))
        items = [t for t in self.todos.values() if t.user_id == user_id]
        if completed is not None:
            items = [t for t in items if t.completed is completed]
        return items[offset : offset + limit]

    async def count_todos_by_user(self, user_id, completed=None):
        items = [t for t in self.todos.values() if t.user_id == user_id]
        if completed is not None:
            items = [t for t in items if t.completed is completed]
        return len(items)

    async def update_todo(self, todo_id: int, dto: UpdateTodoDTO):
        self.calls.append(("update_todo", todo_id, dto))
        todo = self.todos.get(todo_id)
        if not todo:
            return None
        for key, value in dto.model_dump(exclude_unset=True).items():
            setattr(todo, key, value)
        return todo

    async def delete_todo(self, todo_id: int) -> bool:
        self.calls.append(("delete_todo", todo_id))
        return self.todos.pop(todo_id, None) is not None


@pytest.fixture
def repo():
    return FakeTodoRepository(
        [
            Todo(id=1, title="mine", description=None, completed=False, user_id=OWNER),
            Todo(id=2, title="done", description=None, completed=True, user_id=OWNER),
            Todo(id=3, title="theirs", description=None, completed=False, user_id=STRANGER),
        ]
    )


@pytest.fixture
def service(repo):
    return TodoService(repo)


# --- create -----------------------------------------------------------------

async def test_create_todo_assigns_the_owner(service):
    todo = await service.create_todo(OWNER, CreateTodoDTO(title="new"))

    assert todo.title == "new"
    assert todo.user_id == OWNER


async def test_create_todo_defaults_to_incomplete(service):
    todo = await service.create_todo(OWNER, CreateTodoDTO(title="new"))
    assert todo.completed is False


# --- read -------------------------------------------------------------------

async def test_get_todo_returns_an_owned_todo(service):
    assert (await service.get_todo(1, OWNER)).title == "mine"


async def test_get_todo_hides_another_users_todo_as_404(service):
    """404, not 403 — a 403 would confirm the id exists."""
    with pytest.raises(HttpError) as exc:
        await service.get_todo(3, OWNER)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Todo not found"


async def test_get_todo_raises_404_when_missing(service):
    with pytest.raises(HttpError) as exc:
        await service.get_todo(999, OWNER)

    assert exc.value.status_code == 404


# --- list -------------------------------------------------------------------

async def test_list_returns_only_the_callers_todos(service):
    result = await service.list_todos(OWNER)

    assert [t.id for t in result["items"]] == [1, 2]
    assert result["total"] == 2


async def test_list_filters_by_completed(service):
    result = await service.list_todos(OWNER, completed=True)

    assert [t.id for t in result["items"]] == [2]
    assert result["total"] == 1


async def test_list_paginates_and_reports_the_full_total(service):
    result = await service.list_todos(OWNER, limit=1, offset=1)

    assert [t.id for t in result["items"]] == [2]
    assert result["total"] == 2  # total ignores the page window
    assert result["limit"] == 1
    assert result["offset"] == 1


async def test_list_is_empty_for_a_user_with_no_todos(service):
    result = await service.list_todos(999)
    assert result == {"items": [], "total": 0, "limit": 50, "offset": 0}


# --- update -----------------------------------------------------------------

async def test_update_applies_only_provided_fields(service):
    updated = await service.update_todo(1, OWNER, UpdateTodoDTO(completed=True))

    assert updated.completed is True
    assert updated.title == "mine"  # untouched


async def test_update_rejects_an_empty_body(service):
    with pytest.raises(HttpError) as exc:
        await service.update_todo(1, OWNER, UpdateTodoDTO())

    assert exc.value.status_code == 400
    assert exc.value.detail == "No fields to update"


async def test_update_cannot_touch_another_users_todo(service, repo):
    with pytest.raises(HttpError) as exc:
        await service.update_todo(3, OWNER, UpdateTodoDTO(title="hijacked"))

    assert exc.value.status_code == 404
    assert repo.todos[3].title == "theirs"  # unchanged


# --- delete -----------------------------------------------------------------

async def test_delete_removes_an_owned_todo(service, repo):
    assert await service.delete_todo(1, OWNER) is True
    assert 1 not in repo.todos


async def test_delete_cannot_touch_another_users_todo(service, repo):
    with pytest.raises(HttpError) as exc:
        await service.delete_todo(3, OWNER)

    assert exc.value.status_code == 404
    assert 3 in repo.todos  # still there


async def test_delete_raises_404_when_missing(service):
    with pytest.raises(HttpError) as exc:
        await service.delete_todo(999, OWNER)

    assert exc.value.status_code == 404
