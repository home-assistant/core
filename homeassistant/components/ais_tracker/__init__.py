"""AIS tracker."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AisTrackerConfigEntry, AisTrackerCoordinator

LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: AisTrackerConfigEntry) -> bool:
    """Set up config entry."""

    coordinator = AisTrackerCoordinator(hass)
    await coordinator.async_setup()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AisTrackerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
