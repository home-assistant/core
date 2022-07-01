"""Support for LIFX."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, TARGET_ANY
from .coordinator import LIFXUpdateCoordinator
from .discovery import async_discover_devices, async_trigger_discovery
from .manager import LIFXManager
from .migration import async_migrate_entities_devices, async_migrate_legacy_entries
from .util import LIFXConnection, async_entry_is_legacy, get_real_mac_addr

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LIFX component."""
    hass.data[DOMAIN] = {}
    config_entries_by_mac = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if async_entry_is_legacy(entry):
            legacy_entry = entry
        elif entry.unique_id:
            config_entries_by_mac[entry.unique_id] = entry

    discovered_devices = await async_discover_devices(hass)
    hosts_by_mac = {
        get_real_mac_addr(device.mac_addr, device.host_firmware_version): device.ip_addr
        for device in discovered_devices
    }
    if legacy_entry:
        async_migrate_legacy_entries(
            hass, hosts_by_mac, config_entries_by_mac, legacy_entry
        )

    if discovered_devices:
        async_trigger_discovery(hass, discovered_devices)

    async def _async_discovery(*_: Any) -> None:
        if discovered := await async_discover_devices(hass):
            async_trigger_discovery(hass, discovered)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_discovery)
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LIFX from a config entry."""
    if async_entry_is_legacy(entry):
        return True

    legacy_entry: ConfigEntry | None = None
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if async_entry_is_legacy(config_entry):
            legacy_entry = config_entry
            break

    if legacy_entry is not None:
        await async_migrate_entities_devices(hass, legacy_entry.entry_id, entry)

    assert entry.unique_id is not None
    if DATA_LIFX_MANAGER not in hass.data:
        manager = LIFXManager(hass)
        hass.data[DATA_LIFX_MANAGER] = manager
        manager.async_setup()

    host = entry.data[CONF_HOST]
    connection = LIFXConnection(host, TARGET_ANY)
    await connection.async_setup()
    coordinator = LIFXUpdateCoordinator(hass, connection, entry.title)
    coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    device_physical_mac = dr.format_mac(coordinator.physical_mac_address)
    if device_physical_mac != entry.unique_id and entry.unique_id == dr.format_mac(
        coordinator.internal_mac_address
    ):
        # LIFX firmware >= 3.70 uses an off by one mac
        hass.config_entries.async_update_entry(entry, unique_id=device_physical_mac)

    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.connection.async_stop()
    if not hass.data[DOMAIN]:
        hass.data.pop(DATA_LIFX_MANAGER).async_unload()
    return unload_ok
