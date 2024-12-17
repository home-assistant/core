"""Utils for CityBus integration module."""

from typing import NamedTuple


class RouteStop(NamedTuple):
    """NamedTuple for a route, direction, and stop code combination."""

    route_name: str
    direction_destination: str
    stop_code: str
