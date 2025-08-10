"""The Deluge integration."""

from __future__ import annotations

import logging
from ssl import SSLError

from deluge_client.client import DelugeRPCClient

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_WEB_PORT
from .coordinator import DelugeConfigEntry, DelugeDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DelugeConfigEntry) -> bool:
    """Set up Deluge from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    api = await hass.async_add_executor_job(
        DelugeRPCClient, host, port, username, password
    )
    api.web_port = entry.data[CONF_WEB_PORT]
    try:
        await hass.async_add_executor_job(api.connect)
    except (ConnectionRefusedError, TimeoutError, SSLError) as ex:
        raise ConfigEntryNotReady("Connection to Deluge Daemon failed") from ex
    except Exception as ex:
        if type(ex).__name__ == "BadLoginError":
            raise ConfigEntryAuthFailed(
                "Credentials for Deluge client are not valid"
            ) from ex
        _LOGGER.error("Unknown error connecting to Deluge: %s", ex)

    coordinator = DelugeDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DelugeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
