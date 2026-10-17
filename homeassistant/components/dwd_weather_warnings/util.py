"""Util functions for the dwd_weather_warnings integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.location import Coordinates, get_state_coordinates

from .exceptions import CoordinatesNotFoundError, EntityNotFoundError


def get_position_data(hass: HomeAssistant, registry_id: str) -> Coordinates:
    """Extract coordinates from a device tracker."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get(registry_id)
    if registry_entry is None:
        raise EntityNotFoundError(f"Failed to find registry entry {registry_id}")

    if (state := hass.states.get(registry_entry.entity_id)) is None:
        raise EntityNotFoundError(f"Failed to find entity {registry_entry.entity_id}")

    if (coordinates := get_state_coordinates(state)) is None:
        raise CoordinatesNotFoundError(
            f"Failed to find coordinates in {registry_entry.entity_id}"
        )

    return coordinates
