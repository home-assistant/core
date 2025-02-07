"""Helper functions for the WebDAV component."""

from aiowebdav.client import Client

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession


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
    client = Client(
        {
            "webdav_hostname": url,
            "webdav_login": username,
            "webdav_password": password,
        }
    )
    client.verify = verify_ssl
    client.session = async_get_clientsession(hass)
    return client


async def async_ensure_path_exists(client: Client, path: str) -> bool:
    """Ensure that a path exists recursively on the WebDAV server."""
    parts = path.strip("/").split("/")
    for i in range(1, len(parts) + 1):
        sub_path = "/".join(parts[:i])
        if not await client.check(sub_path) and not await client.mkdir(sub_path):
            return False

    return True
