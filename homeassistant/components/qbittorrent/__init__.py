"""The qbittorrent component."""
import logging
import re
from typing import Any

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
)

from .const import DOMAIN
from .coordinator import QBittorrentDataCoordinator
from .helpers import setup_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

MIGRATION_NAME_TO_KEY = {
    # Sensors
    "Download Speed": "download",
    "Upload Speed": "upload",
    "Status": "status",
    "Active Torrents": "active_torrents",
    "Inactive Torrents": "inactive_torrents",
    "Paused Torrents": "paused_torrents",
    "Total Torrents": "total_torrents",
    "Seeding Torrents": "seeding_torrents",
    "Started Torrents": "started_torrents",
}


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up qBittorrent from a config entry."""

    try:
        client = await hass.async_add_executor_job(
            setup_client,
            config_entry.data[CONF_URL],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_VERIFY_SSL],
        )
    except LoginRequired as err:
        raise ConfigEntryNotReady("Invalid credentials") from err
    except RequestException as err:
        raise ConfigEntryNotReady("Failed to connect") from err
    coordinator = QBittorrentDataCoordinator(hass, config_entry, client)
    await hass.async_add_executor_job(coordinator.update)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload qBittorrent config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        del hass.data[DOMAIN][config_entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
