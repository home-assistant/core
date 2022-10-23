"""Support for LIFX."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timedelta
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import _LOGGER, DATA_LIFX_MANAGER, DOMAIN, TARGET_ANY
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


PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.LIGHT, Platform.SELECT]
DISCOVERY_INTERVAL = timedelta(minutes=15)
MIGRATION_INTERVAL = timedelta(minutes=5)

DISCOVERY_COOLDOWN = 5


async def async_legacy_migration(
    hass: HomeAssistant,
    legacy_entry: ConfigEntry,
    discovered_devices: Iterable[Light],
) -> bool:
    """Migrate config entries."""
    existing_serials = {
        entry.unique_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.unique_id and not async_entry_is_legacy(entry)
    }
    # device.mac_addr is not the mac_address, its the serial number
    hosts_by_serial = {device.mac_addr: device.ip_addr for device in discovered_devices}
    missing_discovery_count = async_migrate_legacy_entries(
        hass, hosts_by_serial, existing_serials, legacy_entry
    )
    if missing_discovery_count:
        _LOGGER.info(
            "Migration in progress, waiting to discover %s device(s)",
            missing_discovery_count,
        )
        return False

    _LOGGER.debug(
        "Migration successful, removing legacy entry %s", legacy_entry.entry_id
    )
    await hass.config_entries.async_remove(legacy_entry.entry_id)
    return True


class LIFXDiscoveryManager:
    """Manage discovery and migration."""

    def __init__(self, hass: HomeAssistant, migrating: bool) -> None:
        """Init the manager."""
        self.hass = hass
        self.lock = asyncio.Lock()
        self.migrating = migrating
        self._cancel_discovery: CALLBACK_TYPE | None = None

    @callback
    def async_setup_discovery_interval(self) -> None:
        """Set up discovery at an interval."""
        if self._cancel_discovery:
            self._cancel_discovery()
            self._cancel_discovery = None
        discovery_interval = (
            MIGRATION_INTERVAL if self.migrating else DISCOVERY_INTERVAL
        )
        _LOGGER.debug(
            "LIFX starting discovery with interval: %s and migrating: %s",
            discovery_interval,
            self.migrating,
        )
        self._cancel_discovery = async_track_time_interval(
            self.hass, self.async_discovery, discovery_interval
        )

    async def async_discovery(self, *_: Any) -> None:
        """Discovery and migrate LIFX devics."""
        migrating_was_in_progress = self.migrating

        async with self.lock:
            discovered = await async_discover_devices(self.hass)

            if legacy_entry := async_get_legacy_entry(self.hass):
                migration_complete = await async_legacy_migration(
                    self.hass, legacy_entry, discovered
                )
                if migration_complete and migrating_was_in_progress:
                    self.migrating = False
                    _LOGGER.debug(
                        "LIFX migration complete, switching to normal discovery interval: %s",
                        DISCOVERY_INTERVAL,
                    )
                    self.async_setup_discovery_interval()

            if discovered:
                async_trigger_discovery(self.hass, discovered)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LIFX component."""
    hass.data[DOMAIN] = {}
    migrating = bool(async_get_legacy_entry(hass))
    discovery_manager = LIFXDiscoveryManager(hass, migrating)

    @callback
    def _async_delayed_discovery(now: datetime) -> None:
        """Start an untracked task to discover devices.

        We do not want the discovery task to block startup.
        """
        asyncio.create_task(discovery_manager.async_discovery())

    # Let the system settle a bit before starting discovery
    # to reduce the risk we miss devices because the event
    # loop is blocked at startup.
    discovery_manager.async_setup_discovery_interval()
    async_call_later(hass, DISCOVERY_COOLDOWN, _async_delayed_discovery)
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED, discovery_manager.async_discovery
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LIFX from a config entry."""
    if async_entry_is_legacy(entry):
        return True

    if legacy_entry := async_get_legacy_entry(hass):
        # If the legacy entry still exists, harvest the entities
        # that are moving to this config entry.
        async_migrate_entities_devices(hass, legacy_entry.entry_id, entry)

    assert entry.unique_id is not None
    domain_data = hass.data[DOMAIN]
    if DATA_LIFX_MANAGER not in domain_data:
        manager = LIFXManager(hass)
        domain_data[DATA_LIFX_MANAGER] = manager
        manager.async_setup()

    host = entry.data[CONF_HOST]
    connection = LIFXConnection(host, TARGET_ANY)
    try:
        await connection.async_setup()
    except socket.gaierror as ex:
        connection.async_stop()
        raise ConfigEntryNotReady(f"Could not resolve {host}: {ex}") from ex
    coordinator = LIFXUpdateCoordinator(hass, connection, entry.title)
    coordinator.async_setup()
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        connection.async_stop()
        raise

    domain_data[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if async_entry_is_legacy(entry):
        return True
    domain_data = hass.data[DOMAIN]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LIFXUpdateCoordinator = domain_data.pop(entry.entry_id)
        coordinator.connection.async_stop()
    # Only the DATA_LIFX_MANAGER left, remove it.
    if len(domain_data) == 1:
        manager: LIFXManager = domain_data.pop(DATA_LIFX_MANAGER)
        manager.async_unload()
    return unload_ok
