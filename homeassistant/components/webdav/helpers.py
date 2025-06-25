"""Helper functions for the WebDAV component."""

import logging

from aiowebdav2.client import Client, ClientOptions
from aiowebdav2.exceptions import WebDavError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

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


async def async_migrate_wrong_folder_path(client: Client, path: str) -> None:
    """Migrate the wrong encoded folder path to the correct one."""
    wrong_path = path.replace(" ", "%20")
    # migrate folder when the old folder exists
    if wrong_path != path and await client.check(wrong_path):
        try:
            await client.move(wrong_path, path)
        except WebDavError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="failed_to_migrate_folder",
                translation_placeholders={
                    "wrong_path": wrong_path,
                    "correct_path": path,
                },
            ) from err

        _LOGGER.debug(
            "Migrated wrong encoded folder path from %s to %s", wrong_path, path
        )
