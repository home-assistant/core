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
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector,
)

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
    CONF_ENTRY_ID,
    DEFAULT_DELETE_DATA,
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)
from .coordinator import TransmissionDataUpdateCoordinator
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)

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

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTRY_ID): selector.ConfigEntrySelector(),
    }
)

SERVICE_ADD_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend({vol.Required(ATTR_TORRENT): cv.string}),
)


SERVICE_REMOVE_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ID): cv.positive_int,
            vol.Optional(ATTR_DELETE_DATA, default=DEFAULT_DELETE_DATA): cv.boolean,
        }
    )
)

SERVICE_START_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend({vol.Required(CONF_ID): cv.positive_int}),
)

SERVICE_STOP_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ID): cv.positive_int,
        }
    )
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Transmission Component."""

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        """Update unique ID of entity entry."""
        if CONF_NAME not in config_entry.data:
            return None
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

    coordinator = TransmissionDataUpdateCoordinator(hass, config_entry, api)
    await hass.async_add_executor_job(coordinator.init_torrent_list)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def add_torrent(service: ServiceCall) -> None:
        """Add new torrent to download."""
        torrent = service.data[ATTR_TORRENT]
        if torrent.startswith(
            ("http", "ftp:", "magnet:")
        ) or hass.config.is_allowed_path(torrent):
            await hass.async_add_executor_job(coordinator.api.add_torrent, torrent)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.warning("Could not add torrent: unsupported type or no permission")

    async def start_torrent(service: ServiceCall) -> None:
        """Start torrent."""
        torrent_id = service.data[CONF_ID]
        await hass.async_add_executor_job(coordinator.api.start_torrent, torrent_id)
        await coordinator.async_request_refresh()

    async def stop_torrent(service: ServiceCall) -> None:
        """Stop torrent."""
        torrent_id = service.data[CONF_ID]
        await hass.async_add_executor_job(coordinator.api.stop_torrent, torrent_id)
        await coordinator.async_request_refresh()

    async def remove_torrent(service: ServiceCall) -> None:
        """Remove torrent."""
        torrent_id = service.data[CONF_ID]
        delete_data = service.data[ATTR_DELETE_DATA]
        await hass.async_add_executor_job(
            partial(coordinator.api.remove_torrent, torrent_id, delete_data=delete_data)
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TORRENT, add_torrent, schema=SERVICE_ADD_TORRENT_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TORRENT,
        remove_torrent,
        schema=SERVICE_REMOVE_TORRENT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_TORRENT,
        start_torrent,
        schema=SERVICE_START_TORRENT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_TORRENT,
        stop_torrent,
        schema=SERVICE_STOP_TORRENT_SCHEMA,
    )

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
