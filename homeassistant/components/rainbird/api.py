"""Rain Bird integration API helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import aiohttp
from pyrainbird.async_client import (
    AsyncRainbirdController,
    CreateController,
    create_controller,
)

from .util import normalize_rainbird_host

type _AsyncCreateController = Callable[
    [aiohttp.ClientSession, str, str], Awaitable[AsyncRainbirdController]
]


# In tests, patch `_create_controller` to `None` to force the deterministic
# legacy controller factory path (no probe request ordering differences).
_create_controller: _AsyncCreateController | None = create_controller
_CreateController: Callable[
    [aiohttp.ClientSession, str, str], AsyncRainbirdController
] = CreateController


async def async_create_controller(
    clientsession: aiohttp.ClientSession,
    host: str,
    password: str,
) -> AsyncRainbirdController:
    """Create a pyrainbird controller."""
    host = normalize_rainbird_host(host)
    if _create_controller is not None:
        return await _create_controller(clientsession, host, password)

    return _CreateController(clientsession, host, password)
