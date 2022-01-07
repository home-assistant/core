"""Helpers for Google Time Travel integration."""
from googlemaps import Client
from googlemaps.distance_matrix import distance_matrix
from googlemaps.exceptions import ApiError

from homeassistant.helpers.location import find_coordinates


def is_valid_config_entry(hass, api_key, origin, destination):
    """Return whether the config entry data is valid."""
    origin = find_coordinates(hass, origin)
    destination = find_coordinates(hass, destination)
    client = Client(api_key, timeout=10)
    try:
        distance_matrix(client, origin, destination, mode="driving")
    except ApiError:
        return False
    return True
