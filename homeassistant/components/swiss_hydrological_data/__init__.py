"""The Swiss Hydrological Data integration."""

from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_STATION
from .sensor import HydrologicalData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Swiss Hydrological Data from a config entry."""
    station_id: int = entry.data[CONF_STATION]
    hydro_data = HydrologicalData(station_id)
    try:
        await hass.async_add_executor_job(hydro_data.update)
    except RequestException as err:
        raise ConfigEntryNotReady(
            "Cannot connect to the Swiss Hydrological Data service"
        ) from err

    entry.runtime_data = hydro_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
