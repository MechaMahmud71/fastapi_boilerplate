"""Role-based authorisation guard.

Stack it under @Protected — it reads the user that guard published:

    @router.get("/admin")
    @Protected
    @RoleGuard
    @Roles("admin")
    async def admin_only(user: dict = CurrentUser):
        ...
"""
from src.utils.decorators import ExecutionContext, create_guard, set_metadata

#: Metadata key the guard reads.
ROLES_METADATA_KEY = "roles"

#: Claim on the JWT payload holding the user's role.
ROLE_CLAIM = "role"


def roles_guard(context: ExecutionContext) -> bool:
    """Allow only users whose token carries one of the required roles."""
    required = context.metadata.get(ROLES_METADATA_KEY)
    if not required:
        return True  # no @Roles on the route -> nothing to enforce
    user = context.get("user") or {}
    return user.get(ROLE_CLAIM) in required


def Roles(*roles: str):
    """Declare the roles a route requires — Nest's @Roles(...)."""
    return set_metadata(ROLES_METADATA_KEY, list(roles))


#: Role guard. Returns 403 when the user's role is not in the required list.
RoleGuard = create_guard(
    roles_guard, message="Insufficient permissions", status_code=403
)
