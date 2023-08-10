"""Helpers for Waze Travel Time integration."""
import logging

from pywaze.route_calculator import WazeRouteCalculator, WRCError

from homeassistant.helpers.location import find_coordinates

_LOGGER = logging.getLogger(__name__)


async def is_valid_config_entry(hass, origin, destination, region):
    """Return whether the config entry data is valid."""
    origin = find_coordinates(hass, origin)
    destination = find_coordinates(hass, destination)
    try:
        async with WazeRouteCalculator(region=region) as client:
            await client.calc_all_routes_info(origin, destination)
    except WRCError as error:
        _LOGGER.error("Error trying to validate entry: %s", error)
        return False
    return True
