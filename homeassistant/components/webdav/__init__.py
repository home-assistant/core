"""The WebDAV integration."""

from __future__ import annotations

import logging

from aiowebdav2.client import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_BACKUP_PATH, DATA_BACKUP_AGENT_LISTENERS
from .helpers import async_create_client, async_ensure_path_exists

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

    # Check if we can connect to the WebDAV server
    # and access the root directory
    if not await client.check():
        raise ConfigEntryNotReady("Failed to connect to WebDAV server")

    # Ensure the backup directory exists
    if not await async_ensure_path_exists(
        client, entry.data.get(CONF_BACKUP_PATH, "/")
    ):
        raise ConfigEntryNotReady("Failed to create backup directory")

    entry.runtime_data = client

    _async_notify_backup_listeners_soon(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WebDavConfigEntry) -> bool:
    """Unload a WebDAV config entry."""
    _async_notify_backup_listeners_soon(hass)
    return True


def _async_notify_backup_listeners(hass: HomeAssistant) -> None:
    """Notify all backup listeners."""
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()


@callback
def _async_notify_backup_listeners_soon(hass: HomeAssistant) -> None:
    """Schedule a notification of all backup listeners."""
    hass.loop.call_soon(_async_notify_backup_listeners, hass)
