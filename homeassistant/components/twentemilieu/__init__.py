"""Support for Twente Milieu."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .coordinator import TwenteMilieuConfigEntry, TwenteMilieuDataUpdateCoordinator

SERVICE_UPDATE = "update"
SERVICE_SCHEMA = vol.Schema({vol.Optional(CONF_ID): cv.string})

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> bool:
    """Set up Twente Milieu from a config entry."""
    coordinator = TwenteMilieuDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> bool:
    """Unload Twente Milieu config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
