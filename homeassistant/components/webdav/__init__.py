"""The WebDAV integration."""

from __future__ import annotations

import logging

from aiowebdav2.client import Client
from aiowebdav2.exceptions import UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_BACKUP_PATH, DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .helpers import (
    async_create_client,
    async_ensure_path_exists,
    async_migrate_wrong_folder_path,
)

type WebDavConfigEntry = ConfigEntry[Client]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: WebDavConfigEntry) -> bool:
    """Set up WebDAV from a config entry."""
    client = async_create_client(
        hass=hass,
        url=entry.data[CONF_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )

    try:
        result = await client.check()
    except UnauthorizedError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_username_password",
        ) from err

    # Check if we can connect to the WebDAV server
    # and access the root directory
    if not result:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        )

    path = entry.data.get(CONF_BACKUP_PATH, "/")
    await async_migrate_wrong_folder_path(client, path)

    # Ensure the backup directory exists
    if not await async_ensure_path_exists(client, path):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_access_or_create_backup_path",
        )

    entry.runtime_data = client

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WebDavConfigEntry) -> bool:
    """Unload a WebDAV config entry."""
    return True
