"""Parameter decorator for injecting the authenticated user.

Reads the value published by the authentication guard (@Protected), so the
route must be guarded — on an unguarded route it resolves to None:

    @router.get("/me")
    @Protected
    async def me(user: dict = CurrentUser):
        return user
"""
from utils.decorators import create_param_decorator

#: Key under which @Protected publishes the decoded JWT payload.
USER_CONTEXT_KEY = "user"

#: Inject the authenticated user: `async def me(user: dict = CurrentUser)`
CurrentUser = create_param_decorator(lambda ctx: ctx.get(USER_CONTEXT_KEY))
