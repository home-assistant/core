"""Helpers for Waze Travel Time integration."""

import logging

from pywaze.route_calculator import WazeRouteCalculator, WRCError

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.location import find_coordinates

_LOGGER = logging.getLogger(__name__)


def base_coordinates_to_tuple(
    base_coordinates: dict[str, float] | None,
) -> tuple[float, float] | None:
    """Convert Home Assistant location data to Waze base coordinates."""
    if base_coordinates is None:
        return None

    return (base_coordinates[CONF_LATITUDE], base_coordinates[CONF_LONGITUDE])


def default_base_coordinates_for_region(region: str) -> dict[str, float]:
    """Return pywaze's default base coordinates for a region."""
    base_coordinates = WazeRouteCalculator.BASE_COORDS[region.upper()]
    return {
        CONF_LATITUDE: base_coordinates["lat"],
        CONF_LONGITUDE: base_coordinates["lon"],
    }


async def is_valid_config_entry(
    hass: HomeAssistant, origin: str, destination: str, region: str
) -> bool:
    """Return whether the config entry data is valid."""
    resolved_origin = find_coordinates(hass, origin)
    resolved_destination = find_coordinates(hass, destination)
    httpx_client = get_async_client(hass)
    client = WazeRouteCalculator(region=region, client=httpx_client)
    try:
        await client.calc_routes(resolved_origin, resolved_destination)
    except WRCError as error:
        _LOGGER.error("Error trying to validate entry: %s", error)
        return False
    return True
