"""Util functions for the dwd_weather_warnings integration."""

from __future__ import annotations

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant

from .exceptions import EntityNotFoundError


def get_position_data(
    hass: HomeAssistant, device_tracker: str
) -> tuple[float, float] | None:
    """Extract longitude and latitude from a device tracker."""
    entity = hass.states.get(device_tracker)
    if entity is None:
        raise EntityNotFoundError(f"Failed to find entity {device_tracker}")

    latitude = entity.attributes.get(ATTR_LATITUDE)
    if not latitude:
        raise AttributeError(
            f"Failed to find attribute '{ATTR_LATITUDE}' in {device_tracker}",
            ATTR_LATITUDE,
        )

    longitude = entity.attributes.get(ATTR_LONGITUDE)
    if not longitude:
        raise AttributeError(
            f"Failed to find attribute '{ATTR_LONGITUDE}' in {device_tracker}",
            ATTR_LONGITUDE,
        )

    return (latitude, longitude)
