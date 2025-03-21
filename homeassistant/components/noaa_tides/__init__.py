"""The noaa_tides component."""

from dataclasses import dataclass

from noaa_coops.station import Station
from requests.exceptions import ConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIME_ZONE, CONF_UNIT_SYSTEM, Platform
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import PlatformNotReady

from .const import CONF_STATION_ID, DEFAULT_TIMEZONE, NAME
from .errors import StationNotFound
from .helpers import get_default_unit_system

PLATFORMS = [Platform.SENSOR]

type NoaaTidesConfigEntry = ConfigEntry[NoaaTidesConfigEntryData]


@dataclass
class NoaaTidesConfigEntryData:
    """NOAA Tides data type."""

    station_id: str
    name: str
    timezone: str
    unit_system: str
    station: Station


async def async_setup_entry(
    hass: HomeAssistant, config_entry: NoaaTidesConfigEntry
) -> bool:
    """Set up entry."""
    station_id = config_entry.data.get(CONF_STATION_ID)
    name = config_entry.title
    timezone = config_entry.options.get(CONF_TIME_ZONE, DEFAULT_TIMEZONE)
    unit_system = config_entry.options.get(
        CONF_UNIT_SYSTEM, get_default_unit_system(hass)
    )

    if station_id is None:
        _LOGGER.error("Station ID is required")
        raise StationNotFound

    try:
        station = await hass.async_add_executor_job(Station, station_id, unit_system)
    except KeyError as exception:
        _LOGGER.error("%s sensor station_id %s does not exist", NAME, station_id)
        raise StationNotFound from exception
    except ConnectionError as exception:
        _LOGGER.error(
            "Connection error during setup in %s sensor for station_id: %s",
            NAME,
            station_id,
        )
        raise PlatformNotReady from exception

    config_entry.runtime_data = NoaaTidesConfigEntryData(
        station_id=station_id,
        name=name,
        timezone=timezone,
        unit_system=unit_system,
        station=station,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
