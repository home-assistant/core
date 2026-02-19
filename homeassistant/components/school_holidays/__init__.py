"""The School Holidays integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_REGION, Platform
from homeassistant.core import HomeAssistant

from .coordinator import SchoolHolidaysCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CALENDAR]

type SchoolHolidaysConfigEntry = ConfigEntry[SchoolHolidaysCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SchoolHolidaysConfigEntry
) -> bool:
    """Setup the School Holidays integration."""
    _LOGGER.debug("Starting setup of School Holidays integration")
    coordinator = SchoolHolidaysCoordinator(
        hass,
        entry.data[CONF_COUNTRY],
        entry.data[CONF_REGION],
        entry,
    )

    # Test the connection before setting up platforms.
    # This will raise ConfigEntryNotReady if the API is unavailable.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the School Holidays integration."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
