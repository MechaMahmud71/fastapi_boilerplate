"""Factories for building NestJS-style route decorators.

Three building blocks, mirroring Nest:

* ``create_guard``           -> ``@UseGuards(SomeGuard)`` / ``CanActivate``
* ``set_metadata``           -> ``@SetMetadata('roles', [...])``
* ``create_param_decorator`` -> ``createParamDecorator`` (e.g. ``@CurrentUser()``)

Guards receive an ``ExecutionContext`` and either return ``False`` / raise to
reject the request, or return a value that is stashed on the context for later
guards and param decorators to read.

Example
-------
    is_authenticated = create_guard(jwt_guard, security=bearer_scheme, provides="user")

    @router.get("/me")
    @is_authenticated
    async def me(user: dict = CurrentUser):
        return user
"""
import inspect
from dataclasses import dataclass, field
from functools import wraps
from itertools import count
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from fastapi import Depends, Request
from fastapi.security.base import SecurityBase

from src.utils.expection import HttpError

METADATA_ATTR = "__route_metadata__"
CONTEXT_STATE_KEY = "__guard_context__"

_counter = count()


@dataclass
class ExecutionContext:
    """What a guard is handed, roughly Nest's ExecutionContext."""

    request: Request
    handler: Callable
    credentials: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    #: values returned by guards that declared a ``provides`` name
    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Read a value produced by an earlier guard."""
        return self.data.get(key, default)


GuardFn = Callable[[ExecutionContext], Union[Any, Awaitable[Any]]]


def set_metadata(key: str, value: Any):
    """Attach metadata to a route handler, readable by guards.

    Nest's ``SetMetadata``. Build role decorators on top of it:

        Roles = lambda *roles: set_metadata("roles", list(roles))
    """

    def decorator(func):
        metadata = dict(getattr(func, METADATA_ATTR, {}))
        metadata[key] = value
        setattr(func, METADATA_ATTR, metadata)
        return func

    return decorator


def create_guard(
    guard: GuardFn,
    *,
    security: Optional[SecurityBase] = None,
    provides: Optional[str] = None,
    message: str = "Forbidden",
    status_code: int = 403,
):
    """Build a route decorator that runs ``guard`` before the handler.

    Parameters
    ----------
    guard:
        Sync or async callable taking an ``ExecutionContext``. Return ``False``
        to reject with ``status_code``; raise ``HttpError`` for a custom
        response; return anything else to allow the request.
    security:
        Optional FastAPI security scheme (e.g. ``HTTPBearer``). When given, its
        credentials are injected and exposed as ``context.credentials`` — and
        the route is documented as secured in OpenAPI.
    provides:
        Name under which the guard's return value is stored on the context, so
        later guards and param decorators can read it.
    """

    def decorator(func):
        # Unique parameter name so several guards can stack on one handler.
        guard_param = f"_guard_{next(_counter)}"

        async def run_guard(
            request: Request,
            credentials=(Depends(security) if security is not None else None),
        ):
            """Runs as a FastAPI dependency, so it resolves before the handler's
            own parameters (including any create_param_decorator injections)."""
            context: Optional[ExecutionContext] = getattr(
                request.state, CONTEXT_STATE_KEY, None
            )
            if context is None:
                context = ExecutionContext(request=request, handler=func)
                setattr(request.state, CONTEXT_STATE_KEY, context)

            if credentials is not None:
                context.credentials = credentials
            context.metadata = dict(getattr(wrapper, METADATA_ATTR, {}))

            result = guard(context)
            if inspect.isawaitable(result):
                result = await result

            if result is False:
                raise HttpError(message, status_code)

            if provides:
                context.data[provides] = result

            return result

        # Drop the credentials parameter entirely when no scheme was given, so
        # FastAPI does not see a stray argument.
        if security is None:
            async def run_guard(request: Request):  # noqa: F811
                context: Optional[ExecutionContext] = getattr(
                    request.state, CONTEXT_STATE_KEY, None
                )
                if context is None:
                    context = ExecutionContext(request=request, handler=func)
                    setattr(request.state, CONTEXT_STATE_KEY, context)

                context.metadata = dict(getattr(wrapper, METADATA_ATTR, {}))

                result = guard(context)
                if inspect.isawaitable(result):
                    result = await result

                if result is False:
                    raise HttpError(message, status_code)

                if provides:
                    context.data[provides] = result

                return result

        @wraps(func)
        async def wrapper(*args, **kwargs):
            kwargs.pop(guard_param, None)  # consumed by the dependency above
            return await func(*args, **kwargs)

        # Put the guard dependency FIRST and make every parameter keyword-only,
        # so the guard resolves before the handler's own injected params.
        # FastAPI always calls endpoints with keyword arguments, so this is safe.
        signature = inspect.signature(func)
        original = [
            p.replace(kind=inspect.Parameter.KEYWORD_ONLY)
            for p in signature.parameters.values()
            if p.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        parameters = [
            inspect.Parameter(
                guard_param,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=Depends(run_guard),
                annotation=Any,
            ),
            *original,
        ]
        wrapper.__signature__ = signature.replace(parameters=parameters)

        return wrapper

    return decorator


def create_param_decorator(extractor: Callable[[ExecutionContext], Any]):
    """Build a parameter injector, like Nest's ``createParamDecorator``.

    ``extractor`` receives the ``ExecutionContext`` built by the guards on the
    route. Use the result as a parameter default:

        CurrentUser = create_param_decorator(lambda ctx: ctx.get("user"))

        async def me(user: dict = CurrentUser):
            ...
    """

    async def dependency(request: Request):
        context: Optional[ExecutionContext] = getattr(
            request.state, CONTEXT_STATE_KEY, None
        )
        if context is None:
            # No guard ran on this route; hand over a bare context.
            context = ExecutionContext(request=request, handler=None)
        result = extractor(context)
        if inspect.isawaitable(result):
            result = await result
        return result

    return Depends(dependency)
