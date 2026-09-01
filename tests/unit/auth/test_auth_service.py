"""AuthService business rules, with a fake user service (no database)."""
import jwt
import pytest
from passlib.context import CryptContext

from src.modules.auth.auth_service import AuthService
from src.modules.auth.dtos import LoginDTO, SignupDTO
from src.modules.common.services import config_service
from src.modules.user.user_model import User
from src.utils import HttpError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class FakeUserService:
    """Stands in for UserService; records what it was asked to create."""

    def __init__(self, existing: User = None):
        self.existing = existing
        self.created = None
        self._next_id = 1

    async def get_user_by_username(self, username: str):
        if self.existing and self.existing.username == username:
            return self.existing
        return None

    async def create_user(self, dto):
        self.created = dto
        user = User(id=self._next_id, username=dto.username, password=dto.password)
        self._next_id += 1
        return user


def make_user(username="alice", password="secret123") -> User:
    return User(id=1, username=username, password=pwd_context.hash(password))


def decode(token: str) -> dict:
    return jwt.decode(
        token,
        config_service.get("JWT_SECRET"),
        algorithms=[config_service.get("JWT_ALGORITHM")],
    )


# --- register ---------------------------------------------------------------

async def test_register_returns_user_and_token():
    service = AuthService(FakeUserService())
    result = await service.register(SignupDTO(username="alice", password="secret123"))

    assert set(result) == {"user", "accessToken"}
    assert result["user"].username == "alice"


async def test_register_delegates_hashing_to_the_user_service():
    """AuthService must not hash: UserService does, and hashing twice would
    make the password unverifiable."""
    fake = FakeUserService()
    await AuthService(fake).register(SignupDTO(username="alice", password="secret123"))

    assert fake.created.password == "secret123"


async def test_register_token_carries_username_and_id():
    service = AuthService(FakeUserService())
    result = await service.register(SignupDTO(username="alice", password="secret123"))

    claims = decode(result["accessToken"])
    assert claims["username"] == "alice"
    assert claims["id"] == 1
    assert "exp" in claims


async def test_register_rejects_a_duplicate_username():
    service = AuthService(FakeUserService(existing=make_user()))

    with pytest.raises(HttpError) as exc:
        await service.register(SignupDTO(username="alice", password="secret123"))

    assert exc.value.status_code == 429
    assert "already exists" in exc.value.detail


# --- login ------------------------------------------------------------------

async def test_login_returns_user_and_token():
    service = AuthService(FakeUserService(existing=make_user()))
    result = await service.login(LoginDTO(username="alice", password="secret123"))

    assert result["user"].username == "alice"
    assert decode(result["accessToken"])["username"] == "alice"


async def test_login_rejects_unknown_user():
    service = AuthService(FakeUserService())

    with pytest.raises(HttpError) as exc:
        await service.login(LoginDTO(username="ghost", password="secret123"))

    assert exc.value.status_code == 404
    assert exc.value.detail == "User not found"


async def test_login_rejects_wrong_password():
    service = AuthService(FakeUserService(existing=make_user()))

    with pytest.raises(HttpError) as exc:
        await service.login(LoginDTO(username="alice", password="wrong"))

    assert exc.value.detail == "Password does not match"


async def test_login_response_carries_no_message():
    """Auth routes return the payload bare; the envelope adds the rest."""
    service = AuthService(FakeUserService(existing=make_user()))
    result = await service.login(LoginDTO(username="alice", password="secret123"))

    assert "message" not in result
