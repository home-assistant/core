"""The School Holiday integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_REGION, Platform
from homeassistant.core import HomeAssistant

from .coordinator import SchoolHolidayCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CALENDAR]

type SchoolHolidayConfigEntry = ConfigEntry[SchoolHolidayCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SchoolHolidayConfigEntry
) -> bool:
    """Setup the School Holiday integration."""
    _LOGGER.debug("Starting setup of School Holiday integration")
    coordinator = SchoolHolidayCoordinator(
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
    """Unload the School Holiday integration."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
