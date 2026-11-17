"""Helper functions for the WebDAV component."""

import logging

from aiohttp import ClientTimeout
from aiowebdav2.client import Client, ClientOptions
from aiowebdav2.exceptions import (
    AccessDeniedError,
    ConflictError,
    MethodNotSupportedError,
    RemoteParentNotFoundError,
    ResponseErrorCodeError,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


@callback
def async_create_client(
    *,
    hass: HomeAssistant,
    url: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
) -> Client:
    """Create a WebDAV client."""
    return Client(
        url=url,
        username=username,
        password=password,
        options=ClientOptions(
            verify_ssl=verify_ssl,
            session=async_get_clientsession(hass),
            timeout=ClientTimeout(total=30),
        ),
    )


async def async_ensure_path_exists(client: Client, path: str) -> bool:
    """Ensure the WebDAV server is reachable and a path exists recursively on it."""
    if not await client.exists():
        return False

    if path.strip("/") and not await client.exists(path):
        try:
            await client.mkdir(path, parents=True, exist_ok=True)
        except (
            AccessDeniedError,
            ConflictError,
            MethodNotSupportedError,
            RemoteParentNotFoundError,
            ResponseErrorCodeError,
        ):
            return False

    return True
