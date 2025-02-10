"""Support for the Dynalite networks."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .bridge import DynaliteBridge
from .const import DOMAIN, LOGGER, PLATFORMS
from .convert_config import convert_config
from .panel import async_register_dynalite_frontend
from .services import setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type DynaliteConfigEntry = ConfigEntry[DynaliteBridge]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Dynalite platform."""
    setup_services(hass)

    await async_register_dynalite_frontend(hass)

    return True


async def async_entry_changed(hass: HomeAssistant, entry: DynaliteConfigEntry) -> None:
    """Reload entry since the data has changed."""
    LOGGER.debug("Reconfiguring entry %s", entry.data)
    bridge = entry.runtime_data
    bridge.reload_config(entry.data)
    LOGGER.debug("Reconfiguring entry finished %s", entry.data)


async def async_setup_entry(hass: HomeAssistant, entry: DynaliteConfigEntry) -> bool:
    """Set up a bridge from a config entry."""
    LOGGER.debug("Setting up entry %s", entry.data)
    bridge = DynaliteBridge(hass, convert_config(entry.data))

    if not await bridge.async_setup():
        LOGGER.error("Could not set up bridge for entry %s", entry.data)
        raise ConfigEntryNotReady

    entry.runtime_data = bridge
    entry.async_on_unload(entry.add_update_listener(async_entry_changed))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DynaliteConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading entry %s", entry.data)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
