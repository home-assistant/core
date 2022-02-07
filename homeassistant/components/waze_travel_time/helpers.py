"""Helpers for Waze Travel Time integration."""
from WazeRouteCalculator import WazeRouteCalculator, WRCError

from homeassistant.helpers.location import find_coordinates

from .const import (
    ENTITY_ID_PATTERN,
)

import re

def is_valid_config_entry(hass, origin, destination, region):
    """Return whether the config entry data is valid."""
    cmpl_re = re.compile(ENTITY_ID_PATTERN)

    if cmpl_re.fullmatch(origin):
        if find_coordinates(hass, origin) is not None:
            origin = find_coordinates(hass, origin)
        else:
            origin = hass.states.get(origin).state

    if cmpl_re.fullmatch(destination):
        if find_coordinates(hass, destination) is not None:
            destination = find_coordinates(hass, destination)
        else:
            destination = hass.states.get(destination).state

    try:
        WazeRouteCalculator(origin, destination, region).calc_all_routes_info()
    except WRCError:
        return False
    return True
