"""Support for LIFX."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiolifx.aiolifx import Light
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import LIFXUpdateCoordinator
from .discovery import async_discover_devices, async_trigger_discovery
from .manager import LIFXManager
from .migration import async_migrate_entities_devices
from .util import async_entry_is_legacy

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

    if discovered_devices := await async_discover_devices(hass):
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

    if DATA_LIFX_MANAGER not in hass.data:
        manager = LIFXManager(hass)
        hass.data[DATA_LIFX_MANAGER] = manager
        manager.async_setup()

    host = entry.data[CONF_HOST]
    device = Light(hass.loop, entry.unique_id, host)
    coordinator = LIFXUpdateCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DATA_LIFX_MANAGER).async_unload()
    return unload_ok
