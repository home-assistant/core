"""Helper class for the Ambient Weather Network integration."""

from __future__ import annotations

from typing import Any

from .const import (
    API_LAST_DATA,
    API_STATION_COORDS,
    API_STATION_INFO,
    API_STATION_LOCATION,
    API_STATION_NAME,
    API_STATION_TYPE,
)


def get_station_name(station: dict[str, Any]) -> str:
    """Pick a station name.

    Station names can be empty, in which case we construct the name from
    the location and device type.
    """
    if name := station.get(API_STATION_INFO, {}).get(API_STATION_NAME):
        return str(name)
    location = (
        station.get(API_STATION_INFO, {})
        .get(API_STATION_COORDS, {})
        .get(API_STATION_LOCATION)
    )
    station_type = station.get(API_LAST_DATA, {}).get(API_STATION_TYPE)
    return f"{location}{'' if location is None or station_type is None else ' '}{station_type}"
