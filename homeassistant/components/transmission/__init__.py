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

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_PATH, DEFAULT_SSL, DOMAIN
from .coordinator import TransmissionConfigEntry, TransmissionDataUpdateCoordinator
from .errors import AuthenticationError, CannotConnect, UnknownError
from .services import async_setup_services

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


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Transmission component."""
    async_setup_services(hass)
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

    protocol: Final = "https" if config_entry.data[CONF_SSL] else "http"
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer="Transmission",
        entry_type=DeviceEntryType.SERVICE,
        sw_version=api.server_version,
        configuration_url=(
            f"{protocol}://{config_entry.data[CONF_HOST]}:{config_entry.data[CONF_PORT]}"
        ),
    )

    coordinator = TransmissionDataUpdateCoordinator(hass, config_entry, api)
    await hass.async_add_executor_job(coordinator.init_torrent_list)

    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: TransmissionConfigEntry
) -> bool:
    """Unload Transmission Entry from config_entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: TransmissionConfigEntry
) -> bool:
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
