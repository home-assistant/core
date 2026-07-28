"""The NMBS integration."""

from typing import Final

from pyrail.models import StationDetails

from homeassistant.const import Platform

DOMAIN: Final = "nmbs"

PLATFORMS: Final = [Platform.SENSOR]

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_STATION_LIVE = "station_live"
CONF_EXCLUDE_VIAS = "exclude_vias"


def find_station_by_name(
    stations: list[StationDetails], station_name: str
) -> StationDetails | None:
    """Find given station_name in the station list."""
    return next(
        (s for s in stations if station_name in (s.standard_name, s.name)),
        None,
    )


def find_station(
    stations: list[StationDetails], station_name: str
) -> StationDetails | None:
    """Find given station_id in the station list."""
    return next(
        (s for s in stations if station_name in s.id),
        None,
    )
