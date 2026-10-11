"""The NMBS component."""

from dataclasses import dataclass
import logging

from pyrail import iRail
from pyrail.models import StationDetails

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

from .const import CONF_STATION_FROM, CONF_STATION_TO, DOMAIN, find_station

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


@dataclass
class NMBSData:
    """Data for an NMBS config entry."""

    station_from: StationDetails
    station_to: StationDetails


type NMBSConfigEntry = ConfigEntry[NMBSData]

NMBS_KEY: HassKey[list[StationDetails]] = HassKey(DOMAIN)


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@singleton(NMBS_KEY, async_=True)
async def _async_get_stations(hass: HomeAssistant) -> list[StationDetails]:
    """Fetch the station list, which is shared by all entries."""
    api_client = iRail(session=async_get_clientsession(hass))
    station_response = await api_client.get_stations()
    if station_response is None:
        raise ConfigEntryNotReady(
            "Unable to fetch the NMBS station list; the iRail API is unavailable"
        )
    return station_response.stations


async def async_setup_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> bool:
    """Set up NMBS from a config entry."""
    stations = await _async_get_stations(hass)
    station_from = find_station(stations, entry.data[CONF_STATION_FROM])
    station_to = find_station(stations, entry.data[CONF_STATION_TO])
    if station_from is None or station_to is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="station_not_found",
            translation_placeholders={
                "station": entry.data[CONF_STATION_FROM]
                if station_from is None
                else entry.data[CONF_STATION_TO]
            },
        )
    entry.runtime_data = NMBSData(station_from=station_from, station_to=station_to)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NMBSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
