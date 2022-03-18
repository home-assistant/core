"""Helpers for Waze Travel Time integration."""
from WazeRouteCalculator import WazeRouteCalculator, WRCError

from homeassistant.helpers.location import find_coordinates


def is_valid_config_entry(hass, origin, destination, region):
    """Return whether the config entry data is valid."""
    origin = find_coordinates(hass, origin)
    destination = find_coordinates(hass, destination)
    try:
        WazeRouteCalculator(origin, destination, region).calc_all_routes_info()
    except WRCError:
        return False
    return True
