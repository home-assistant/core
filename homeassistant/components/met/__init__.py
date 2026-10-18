"""The met component."""

from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import (
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
)
from .coordinator import MetDataUpdateCoordinator, MetWeatherConfigEntry

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MetWeatherConfigEntry
) -> None:
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
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_home_location",
        )

    coordinator = MetDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    if config_entry.data.get(CONF_TRACK_HOME, False):
        coordinator.track_home()

    config_entry.runtime_data = coordinator

    config_entry.async_on_unload(coordinator.untrack_home)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MetWeatherConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: MetWeatherConfigEntry
) -> bool:
    """Migrate old config entry."""
    if config_entry.minor_version < 2:
        data = dict(config_entry.data)
        data.pop(CONF_NAME, None)

        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            minor_version=2,
        )

    return True
