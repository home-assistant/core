"""The met component."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_TRACK_HOME, DEFAULT_HOME_LATITUDE, DEFAULT_HOME_LONGITUDE
from .coordinator import MetDataUpdateCoordinator, MetWeatherConfigEntry

PLATFORMS = [Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MetWeatherConfigEntry
) -> bool:
    """Set up Met as config entry."""
    # Don't setup if tracking home location and latitude or longitude isn't set.
    # Also, filters out our onboarding default location.
    if config_entry.data.get(CONF_TRACK_HOME, False) and (
        (not hass.config.latitude and not hass.config.longitude)
        or (
            hass.config.latitude == DEFAULT_HOME_LATITUDE
            and hass.config.longitude == DEFAULT_HOME_LONGITUDE
        )
    ):
        _LOGGER.warning(
            "Skip setting up met.no integration; No Home location has been set"
        )
        return False

    coordinator = MetDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    if config_entry.data.get(CONF_TRACK_HOME, False):
        coordinator.track_home()

    config_entry.runtime_data = coordinator

    config_entry.async_on_unload(coordinator.untrack_home)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MetWeatherConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
