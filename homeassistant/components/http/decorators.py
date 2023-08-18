"""Decorators for the Home Assistant API."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar, overload

from aiohttp.web import Request, Response

from homeassistant.exceptions import Unauthorized

from .view import HomeAssistantView

_HomeAssistantViewT = TypeVar("_HomeAssistantViewT", bound=HomeAssistantView)
_P = ParamSpec("_P")
_FuncType = Callable[
    Concatenate[_HomeAssistantViewT, Request, _P], Coroutine[Any, Any, Response]
]


@overload
def require_admin(
    _func: None = None,
    *,
    error: Unauthorized | None = None,
) -> Callable[[_FuncType[_HomeAssistantViewT, _P]], _FuncType[_HomeAssistantViewT, _P]]:
    ...


@overload
def require_admin(
    _func: _FuncType[_HomeAssistantViewT, _P],
) -> _FuncType[_HomeAssistantViewT, _P]:
    ...


def require_admin(
    _func: _FuncType[_HomeAssistantViewT, _P] | None = None,
    *,
    error: Unauthorized | None = None,
) -> (
    Callable[[_FuncType[_HomeAssistantViewT, _P]], _FuncType[_HomeAssistantViewT, _P]]
    | _FuncType[_HomeAssistantViewT, _P]
):
    """Home Assistant API decorator to require user to be an admin."""

    def decorator_require_admin(
        func: _FuncType[_HomeAssistantViewT, _P]
    ) -> _FuncType[_HomeAssistantViewT, _P]:
        """Wrap the provided with_admin function."""

        @wraps(func)
        async def with_admin(
            self: _HomeAssistantViewT,
            request: Request,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> Response:
            """Check admin and call function."""
            if not request["hass_user"].is_admin:
                raise error or Unauthorized()

            return await func(self, request, *args, **kwargs)

        return with_admin

    # See if we're being called as @require_admin or @require_admin().
    if _func is None:
        # We're called with brackets.
        return decorator_require_admin

    # We're called as @require_admin without brackets.
    return decorator_require_admin(_func)
