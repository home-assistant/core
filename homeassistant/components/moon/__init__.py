"""The Moon integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .helpers import MoonConfigEntry, load_moon_data


async def async_setup_entry(hass: HomeAssistant, entry: MoonConfigEntry) -> None:
    """Set up from a config entry."""
    try:
        entry.runtime_data = await hass.async_add_executor_job(
            load_moon_data, hass.config.path(".storage", entry.domain, "skyfield")
        )
    except OSError as err:
        raise ConfigEntryNotReady("Unable to download the Skyfield ephemeris") from err

    entry.async_on_unload(entry.runtime_data.ephemeris.close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
