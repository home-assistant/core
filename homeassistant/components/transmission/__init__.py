"""Support for the Transmission BitTorrent client API."""
from __future__ import annotations

from functools import partial
import logging
import re
from typing import Any

import transmission_rpc
from transmission_rpc.error import (
    TransmissionAuthError,
    TransmissionConnectError,
    TransmissionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)
from .coordinator import TransmissionDataUpdateCoordinator
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

MIGRATION_NAME_TO_KEY = {
    # Sensors
    "Down Speed": "download",
    "Up Speed": "upload",
    "Status": "status",
    "Active Torrents": "active_torrents",
    "Paused Torrents": "paused_torrents",
    "Total Torrents": "total_torrents",
    "Completed Torrents": "completed_torrents",
    "Started Torrents": "started_torrents",
    # Switches
    "Switch": "on_off",
    "Turtle Mode": "turtle_mode",
}


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Transmission Component."""

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        """Update unique ID of entity entry."""
        match = re.search(
            f"{config_entry.data[CONF_HOST]}-{config_entry.data[CONF_NAME]} (?P<name>.+)",
            entity_entry.unique_id,
        )

        if match and (key := MIGRATION_NAME_TO_KEY.get(match.group("name"))):
            return {"new_unique_id": f"{config_entry.entry_id}-{key}"}
        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    try:
        api = await get_api(hass, dict(config_entry.data))
    except CannotConnect as error:
        raise ConfigEntryNotReady from error
    except (AuthenticationError, UnknownError) as error:
        raise ConfigEntryAuthFailed from error

    client = TransmissionDataUpdateCoordinator(hass, config_entry, api)
    await client.async_setup()
    await client.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    client.register_services()
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Transmission Entry from config_entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_START_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_STOP_TORRENT)

    return unload_ok


async def get_api(
    hass: HomeAssistant, entry: dict[str, Any]
) -> transmission_rpc.Client:
    """Get Transmission client."""
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        api = await hass.async_add_executor_job(
            partial(
                transmission_rpc.Client,
                username=username,
                password=password,
                host=host,
                port=port,
            )
        )
        _LOGGER.debug("Successfully connected to %s", host)
        return api

    except TransmissionAuthError as error:
        _LOGGER.error("Credentials for Transmission client are not valid")
        raise AuthenticationError from error
    except TransmissionConnectError as error:
        _LOGGER.error("Connecting to the Transmission client %s failed", host)
        raise CannotConnect from error
    except TransmissionError as error:
        _LOGGER.error(error)
        raise UnknownError from error
