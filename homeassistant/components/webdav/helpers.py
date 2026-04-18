"""Helper functions for the WebDAV component."""

import logging

from aiowebdav2.client import Client, ClientOptions

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
        ),
    )


async def async_ensure_path_exists(client: Client, path: str) -> bool:
    """Ensure that a path exists recursively on the WebDAV server."""
    parts = path.strip("/").split("/")
    for i in range(1, len(parts) + 1):
        sub_path = "/".join(parts[:i])
        if not await client.check(sub_path) and not await client.mkdir(sub_path):
            return False

    return True
