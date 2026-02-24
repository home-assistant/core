"""Rain Bird integration API helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import suppress

import aiohttp
from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController

from .util import normalize_rainbird_host

type _AsyncCreateController = Callable[
    [aiohttp.ClientSession, str, str], Awaitable[AsyncRainbirdController]
]

_create_controller: _AsyncCreateController | None = None
with suppress(ImportError):  # pragma: no cover
    from pyrainbird.async_client import create_controller as _imported_create_controller

    _create_controller = _imported_create_controller

_CreateController: Callable[[aiohttp.ClientSession, str, str], AsyncRainbirdController] | None = None
with suppress(ImportError):  # pragma: no cover
    from pyrainbird.async_client import CreateController as _imported_CreateController

    _CreateController = _imported_CreateController


async def async_create_controller(
    clientsession: aiohttp.ClientSession,
    host: str,
    password: str,
) -> AsyncRainbirdController:
    """Create a pyrainbird controller.

    This wrapper supports both pyrainbird 6.0.x (host-based) and pyrainbird 6.1.x
    (controller discovery via `create_controller`).
    """
    host = normalize_rainbird_host(host)

    if _create_controller is not None:
        return await _create_controller(clientsession, host, password)

    if _CreateController is not None:
        return _CreateController(clientsession, host, password)

    # pyrainbird 6.1.0 changed AsyncRainbirdClient to be URL-based. When neither
    # controller factory is available, fall back to the legacy HTTP endpoint.
    try:
        local_client = AsyncRainbirdClient(
            clientsession, f"http://{host}/stick", password
        )
    except TypeError:
        local_client = AsyncRainbirdClient(clientsession, host, password)

    return AsyncRainbirdController(local_client)
