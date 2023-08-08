"""Decorators for the Home Assistant API."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Concatenate, ParamSpec, TypeVar

from aiohttp.web import Request, Response

from homeassistant.exceptions import Unauthorized

from .view import HomeAssistantView

_HomeAssistantViewT = TypeVar("_HomeAssistantViewT", bound=HomeAssistantView)
_P = ParamSpec("_P")


def require_admin(
    func: Callable[Concatenate[_HomeAssistantViewT, Request, _P], Awaitable[Response]]
) -> Callable[Concatenate[_HomeAssistantViewT, Request, _P], Awaitable[Response]]:
    """Home Assistant API decorator to require user to be an admin."""

    async def with_admin(
        self: _HomeAssistantViewT, request: Request, *args: _P.args, **kwargs: _P.kwargs
    ) -> Response:
        """Check admin and call function."""
        if not request["hass_user"].is_admin:
            raise Unauthorized()

        return await func(self, request, *args, **kwargs)

    return with_admin
