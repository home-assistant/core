"""The PID controller integration."""

from __future__ import annotations

import logging

from homeassistant.components.pid_controller import async_setup as async_pid_setup
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

PLATFORMS = [Platform.CLIMATE]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up slow PID Controller from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services for PID thermostat."""
    return await async_pid_setup(hass, config)


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
