"""The NMBS integration."""

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN: Final = "nmbs"

PLATFORMS: Final = [Platform.SENSOR]

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_STATION_LIVE = "station_live"
CONF_EXCLUDE_VIAS = "exclude_vias"
CONF_SHOW_ON_MAP = "show_on_map"


def find_station_by_name(hass: HomeAssistant, station_name: str):
    """Find given station_name in the station list."""
    return next(
        (
            s
            for s in hass.data[DOMAIN]
            if station_name in (s["standardname"], s["name"])
        ),
        None,
    )


def find_station(hass: HomeAssistant, station_name: str):
    """Find given station_id in the station list."""
    return next(
        (s for s in hass.data[DOMAIN] if station_name in s["id"]),
        None,
    )
