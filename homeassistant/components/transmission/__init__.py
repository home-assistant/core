"""Support for the Transmission BitTorrent client API."""

from __future__ import annotations

from functools import partial
import logging
import re
from typing import Any, Final

import transmission_rpc
from transmission_rpc.error import (
    TransmissionAuthError,
    TransmissionConnectError,
    TransmissionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
    CONF_ENTRY_ID,
    DEFAULT_DELETE_DATA,
    DEFAULT_PATH,
    DEFAULT_SSL,
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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TransmissionConfigEntry = ConfigEntry[TransmissionDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Transmission component."""
    setup_hass_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: TransmissionConfigEntry
) -> bool:
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
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Transmission Entry from config_entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version == 1:
        # Version 1.2 adds ssl and path
        if config_entry.minor_version < 2:
            new = {**config_entry.data}

            new[CONF_PATH] = DEFAULT_PATH
            new[CONF_SSL] = DEFAULT_SSL

        hass.config_entries.async_update_entry(
            config_entry, data=new, version=1, minor_version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


def _get_coordinator_from_service_data(
    hass: HomeAssistant, entry_id: str
) -> TransmissionDataUpdateCoordinator:
    """Return coordinator for entry id."""
    entry: TransmissionConfigEntry | None = hass.config_entries.async_get_entry(
        entry_id
    )
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(f"Config entry {entry_id} is not found or not loaded")
    return entry.runtime_data


def setup_hass_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    async def add_torrent(service: ServiceCall) -> None:
        """Add new torrent to download."""
        entry_id: str = service.data[CONF_ENTRY_ID]
        coordinator = _get_coordinator_from_service_data(hass, entry_id)
        torrent: str = service.data[ATTR_TORRENT]
        if torrent.startswith(
            ("http", "ftp:", "magnet:")
        ) or hass.config.is_allowed_path(torrent):
            await hass.async_add_executor_job(coordinator.api.add_torrent, torrent)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.warning("Could not add torrent: unsupported type or no permission")

    async def start_torrent(service: ServiceCall) -> None:
        """Start torrent."""
        entry_id: str = service.data[CONF_ENTRY_ID]
        coordinator = _get_coordinator_from_service_data(hass, entry_id)
        torrent_id = service.data[CONF_ID]
        await hass.async_add_executor_job(coordinator.api.start_torrent, torrent_id)
        await coordinator.async_request_refresh()

    async def stop_torrent(service: ServiceCall) -> None:
        """Stop torrent."""
        entry_id: str = service.data[CONF_ENTRY_ID]
        coordinator = _get_coordinator_from_service_data(hass, entry_id)
        torrent_id = service.data[CONF_ID]
        await hass.async_add_executor_job(coordinator.api.stop_torrent, torrent_id)
        await coordinator.async_request_refresh()

    async def remove_torrent(service: ServiceCall) -> None:
        """Remove torrent."""
        entry_id: str = service.data[CONF_ENTRY_ID]
        coordinator = _get_coordinator_from_service_data(hass, entry_id)
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


async def get_api(
    hass: HomeAssistant, entry: dict[str, Any]
) -> transmission_rpc.Client:
    """Get Transmission client."""
    protocol: Final = "https" if entry[CONF_SSL] else "http"
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    path = entry[CONF_PATH]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        api = await hass.async_add_executor_job(
            partial(
                transmission_rpc.Client,
                username=username,
                password=password,
                protocol=protocol,
                host=host,
                port=port,
                path=path,
            )
        )
    except TransmissionAuthError as error:
        _LOGGER.error("Credentials for Transmission client are not valid")
        raise AuthenticationError from error
    except TransmissionConnectError as error:
        _LOGGER.error("Connecting to the Transmission client %s failed", host)
        raise CannotConnect from error
    except TransmissionError as error:
        _LOGGER.error(error)
        raise UnknownError from error
    _LOGGER.debug("Successfully connected to %s", host)
    return api
