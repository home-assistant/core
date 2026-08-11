"""The usgs_earthquakes_feed component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

type UsgsEarthquakesFeedConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: UsgsEarthquakesFeedConfigEntry
) -> bool:
    """Set up USGS Earthquakes Feed from a config entry."""
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UsgsEarthquakesFeedConfigEntry
) -> bool:
    """Unload a USGS Earthquakes Feed config entry."""
    return True
