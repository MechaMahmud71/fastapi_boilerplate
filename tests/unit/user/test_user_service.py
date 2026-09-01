"""UserService delegation, with a fake repository (no database)."""
import pytest

from src.utils import HttpError
from src.utils.security import verify_password

from src.modules.user.dtos import CreateUserDTO, UpdateUserDTO
from src.modules.user.user_model import User
from src.modules.user.user_service import UserService


class FakeUserRepository:
    """In-memory stand-in for UserRepository."""

    def __init__(self, users=None):
        self.users = {user.id: user for user in (users or [])}
        self.calls = []
        self._next_id = max(self.users, default=0) + 1

    async def create_user(self, dto: CreateUserDTO) -> User:
        self.calls.append(("create_user", dto))
        user = User(id=self._next_id, username=dto.username, password=dto.password)
        self.users[user.id] = user
        self._next_id += 1
        return user

    async def get_user_by_id(self, user_id: int):
        self.calls.append(("get_user_by_id", user_id))
        return self.users.get(user_id)

    async def get_all_users(self):
        self.calls.append(("get_all_users",))
        return list(self.users.values())

    async def update_user(self, user_id: int, dto: UpdateUserDTO):
        self.calls.append(("update_user", user_id, dto))
        user = self.users.get(user_id)
        if not user:
            return None
        for key, value in dto.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        return user

    async def delete_user(self, user_id: int) -> bool:
        self.calls.append(("delete_user", user_id))
        return self.users.pop(user_id, None) is not None

    async def get_user_by_username(self, username: str):
        self.calls.append(("get_user_by_username", username))
        return next((u for u in self.users.values() if u.username == username), None)


@pytest.fixture
def repo():
    return FakeUserRepository([User(id=1, username="alice", password="hashed")])


@pytest.fixture
def service(repo):
    return UserService(repo)


async def test_create_user_delegates_to_the_repository(service, repo):
    user = await service.create_user(CreateUserDTO(username="bob", password="pw"))

    assert user.username == "bob"
    assert repo.calls[-1][0] == "create_user"


async def test_create_user_hashes_the_password(service, repo):
    await service.create_user(CreateUserDTO(username="bob", password="pw"))

    stored = repo.calls[-1][1].password
    assert stored != "pw"
    assert verify_password("pw", stored)


async def test_create_user_rejects_a_duplicate_username(service):
    with pytest.raises(HttpError) as exc:
        await service.create_user(CreateUserDTO(username="alice", password="pw"))

    assert exc.value.status_code == 409


async def test_get_user_returns_the_match(service):
    assert (await service.get_user(1)).username == "alice"


async def test_get_user_raises_404_when_missing(service):
    with pytest.raises(HttpError) as exc:
        await service.get_user(999)

    assert exc.value.status_code == 404
    assert exc.value.detail == "User not found"


async def test_get_all_users(service):
    assert [u.username for u in await service.get_all_users()] == ["alice"]


async def test_update_user_applies_only_provided_fields(service, repo):
    updated = await service.update_user(1, UpdateUserDTO(username="alice2"))

    assert updated.username == "alice2"
    assert updated.password == "hashed"  # untouched


async def test_update_user_raises_404_when_missing(service):
    with pytest.raises(HttpError) as exc:
        await service.update_user(999, UpdateUserDTO(username="x"))

    assert exc.value.status_code == 404


async def test_update_user_rejects_an_empty_body(service):
    with pytest.raises(HttpError) as exc:
        await service.update_user(1, UpdateUserDTO())

    assert exc.value.status_code == 400
    assert exc.value.detail == "No fields to update"


async def test_update_user_hashes_a_new_password(service, repo):
    await service.update_user(1, UpdateUserDTO(password="newpw"))

    assert verify_password("newpw", repo.users[1].password)


async def test_update_user_rejects_a_taken_username(service, repo):
    repo.users[2] = User(id=2, username="bob", password="hashed")

    with pytest.raises(HttpError) as exc:
        await service.update_user(1, UpdateUserDTO(username="bob"))

    assert exc.value.status_code == 409


async def test_delete_user_reports_success(service):
    assert await service.delete_user(1) is True


async def test_delete_user_raises_404_when_missing(service):
    with pytest.raises(HttpError) as exc:
        await service.delete_user(999)

    assert exc.value.status_code == 404


async def test_get_user_by_username(service):
    assert (await service.get_user_by_username("alice")).id == 1
    assert await service.get_user_by_username("nobody") is None
