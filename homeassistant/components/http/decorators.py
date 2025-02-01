"""Decorators for the Home Assistant API."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, overload

from aiohttp.web import Request, Response, StreamResponse

from homeassistant.auth.models import User
from homeassistant.exceptions import Unauthorized

from .view import HomeAssistantView

type _ResponseType = Response | StreamResponse
type _FuncType[_T, **_P, _R] = Callable[
    Concatenate[_T, Request, _P], Coroutine[Any, Any, _R]
]


@overload
def require_admin[
    _HomeAssistantViewT: HomeAssistantView,
    **_P,
    _ResponseT: _ResponseType,
](
    _func: None = None,
    *,
    error: Unauthorized | None = None,
) -> Callable[
    [_FuncType[_HomeAssistantViewT, _P, _ResponseT]],
    _FuncType[_HomeAssistantViewT, _P, _ResponseT],
]: ...


@overload
def require_admin[
    _HomeAssistantViewT: HomeAssistantView,
    **_P,
    _ResponseT: _ResponseType,
](
    _func: _FuncType[_HomeAssistantViewT, _P, _ResponseT],
) -> _FuncType[_HomeAssistantViewT, _P, _ResponseT]: ...


def require_admin[
    _HomeAssistantViewT: HomeAssistantView,
    **_P,
    _ResponseT: _ResponseType,
](
    _func: _FuncType[_HomeAssistantViewT, _P, _ResponseT] | None = None,
    *,
    error: Unauthorized | None = None,
) -> (
    Callable[
        [_FuncType[_HomeAssistantViewT, _P, _ResponseT]],
        _FuncType[_HomeAssistantViewT, _P, _ResponseT],
    ]
    | _FuncType[_HomeAssistantViewT, _P, _ResponseT]
):
    """Home Assistant API decorator to require user to be an admin."""

    def decorator_require_admin(
        func: _FuncType[_HomeAssistantViewT, _P, _ResponseT],
    ) -> _FuncType[_HomeAssistantViewT, _P, _ResponseT]:
        """Wrap the provided with_admin function."""

        @wraps(func)
        async def with_admin(
            self: _HomeAssistantViewT,
            request: Request,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> _ResponseT:
            """Check admin and call function."""
            user: User = request["hass_user"]
            if not user.is_admin:
                raise error or Unauthorized()

            return await func(self, request, *args, **kwargs)

        return with_admin

    # See if we're being called as @require_admin or @require_admin().
    if _func is None:
        # We're called with brackets.
        return decorator_require_admin

    # We're called as @require_admin without brackets.
    return decorator_require_admin(_func)
