"""The NMBS integration."""

from typing import Final

from pyrail.models import StationDetails

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "nmbs"
NMBS_STATION_DATA: HassKey[list[StationDetails]] = HassKey(DOMAIN)

PLATFORMS: Final = [Platform.SENSOR]

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_STATION_LIVE = "station_live"
CONF_EXCLUDE_VIAS = "exclude_vias"


def find_station_by_name(hass: HomeAssistant, station_name: str):
    """Find given station_name in the station list."""
    return next(
        (
            s
            for s in hass.data[NMBS_STATION_DATA]
            if station_name in (s.standard_name, s.name)
        ),
        None,
    )


def find_station(hass: HomeAssistant, station_name: str):
    """Find given station_id in the station list."""
    return next(
        (s for s in hass.data[NMBS_STATION_DATA] if station_name in s.id),
        None,
    )
