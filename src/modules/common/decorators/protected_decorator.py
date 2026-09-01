"""Authentication guard, built with the factories in utils.decorators."""
import jwt
from fastapi.security import HTTPBearer

from src.modules.common.services import config_service
from src.utils.decorators import ExecutionContext, create_guard
from src.utils.expection import HttpError

# auto_error=False: we raise HttpError ourselves so failures come out in the
# standard error envelope instead of FastAPI's bare {"detail": ...}.
bearer_scheme = HTTPBearer(auto_error=False)

UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def jwt_guard(context: ExecutionContext) -> dict:
    """Verify the bearer token and return its decoded payload."""
    credentials = context.credentials
    if credentials is None or not credentials.credentials:
        raise HttpError("Token not found", 401, UNAUTHORIZED_HEADERS)

    try:
        decoded_user = jwt.decode(
            credentials.credentials,
            config_service.get("JWT_SECRET"),
            algorithms=[config_service.get("JWT_ALGORITHM")],
        )
    except jwt.ExpiredSignatureError:
        raise HttpError("Token Expired", 401, UNAUTHORIZED_HEADERS)
    except jwt.InvalidTokenError:
        raise HttpError("Invalid Token", 401, UNAUTHORIZED_HEADERS)

    # Kept for backwards compatibility with helpers.get_current_user.
    context.request.state.user = decoded_user
    return decoded_user


#: Auth guard. Rejects a missing/invalid/expired token with 401 and publishes
#: the decoded payload as "user" for later guards and CurrentUser.
Protected = create_guard(jwt_guard, security=bearer_scheme, provides="user")