"""The rejseplanen component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_AUTHENTICATION, DOMAIN
from .coordinator import RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    _LOGGER.info(
        "Setting up Rejseplanen integration for entry: %s", config_entry.entry_id
    )
    hass.data.setdefault(DOMAIN, {})

    coordinator = RejseplanenDataUpdateCoordinator(
        hass, config_entry.data[CONF_AUTHENTICATION]
    )
    hass.data[DOMAIN][config_entry.entry_id] = {
        "coordinator": coordinator,
        "stop_data": None,  # Will be set by subentries/sensors
    }

    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.SENSOR]
    )

    await coordinator.async_config_entry_first_refresh()
    return True
