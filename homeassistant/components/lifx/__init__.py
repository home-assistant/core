"""Support for LIFX."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timedelta
import logging
import socket
from typing import Any

from aiolifx.aiolifx import Light
from aiolifx.connection import LIFXConnection
import voluptuous as vol

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, TARGET_ANY
from .coordinator import LIFXUpdateCoordinator
from .discovery import async_discover_devices, async_trigger_discovery
from .manager import LIFXManager
from .migration import async_migrate_entities_devices, async_migrate_legacy_entries
from .util import async_entry_is_legacy, async_get_legacy_entry

CONF_SERVER = "server"
CONF_BROADCAST = "broadcast"


INTERFACE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SERVER): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_BROADCAST): cv.string,
    }
)

CONFIG_SCHEMA = vol.All(
    cv.deprecated(DOMAIN),
    vol.Schema(
        {
            DOMAIN: {
                LIGHT_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [INTERFACE_SCHEMA]))
            }
        },
        extra=vol.ALLOW_EXTRA,
    ),
)

DATA_LIFX_MANAGER = "lifx_manager"

PLATFORMS = [Platform.LIGHT]
DISCOVERY_INTERVAL = timedelta(minutes=15)

DISCOVERY_COOLDOWN = 5
_LOGGER = logging.getLogger(__name__)


async def async_legacy_migration(
    hass: HomeAssistant,
    legacy_entry: ConfigEntry,
    discovered_devices: Iterable[Light],
) -> None:
    """Migrate config entries."""
    existing_serials = {
        entry.unique_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.unique_id and not async_entry_is_legacy(entry)
    }
    # device.mac_addr not the mac_address, its the serial number
    hosts_by_serial = {device.mac_addr: device.ip_addr for device in discovered_devices}
    missing_discovery_count = await async_migrate_legacy_entries(
        hass, hosts_by_serial, existing_serials, legacy_entry
    )
    if missing_discovery_count:
        _LOGGER.info(
            "Migration in progress, waiting to discover %s device(s)",
            missing_discovery_count,
        )
        return

    _LOGGER.debug(
        "Migration successful, removing legacy entry %s", legacy_entry.entry_id
    )
    await hass.config_entries.async_remove(legacy_entry.entry_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LIFX component."""
    hass.data[DOMAIN] = {}
    discovery_lock = asyncio.Lock()

    async def _async_discovery(*_: Any) -> None:
        async with discovery_lock:
            if discovered := await async_discover_devices(hass):
                if legacy_entry := async_get_legacy_entry(hass):
                    await async_legacy_migration(hass, legacy_entry, discovered)
                async_trigger_discovery(hass, discovered)

    @callback
    def _async_delayed_discovery(now: datetime) -> None:
        asyncio.create_task(_async_discovery())

    # Let the system settle a bit before starting discovery
    # to reduce the risk we miss devices because the event
    # loop is blocked at startup.
    async_call_later(hass, DISCOVERY_COOLDOWN, _async_delayed_discovery)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_discovery)
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LIFX from a config entry."""
    if async_entry_is_legacy(entry):
        return True

    if legacy_entry := async_get_legacy_entry(hass):
        # If the legacy entry still exists, harvest the entities
        # that are moving to this config entry.
        await async_migrate_entities_devices(hass, legacy_entry.entry_id, entry)

    assert entry.unique_id is not None
    if DATA_LIFX_MANAGER not in hass.data:
        manager = LIFXManager(hass)
        hass.data[DATA_LIFX_MANAGER] = manager
        manager.async_setup()

    host = entry.data[CONF_HOST]
    connection = LIFXConnection(host, TARGET_ANY)
    try:
        await connection.async_setup()
    except socket.gaierror as ex:
        raise ConfigEntryNotReady(f"Could not resolve {host}: {ex}") from ex
    coordinator = LIFXUpdateCoordinator(hass, connection, entry.title)
    coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if async_entry_is_legacy(entry):
        return True
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.connection.async_stop()
    if not hass.data[DOMAIN]:
        hass.data.pop(DATA_LIFX_MANAGER).async_unload()
    return unload_ok
