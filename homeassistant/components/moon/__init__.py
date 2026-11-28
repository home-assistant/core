"""The Moon integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .helpers import async_get_moon_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up from a config entry."""
    try:
        await async_get_moon_data(hass)
    except OSError as err:
        raise ConfigEntryNotReady("Unable to download the Skyfield ephemeris") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
