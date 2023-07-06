"""Util functions for the dwd_weather_warnings integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import LOGGER


def get_position_data(
    hass: HomeAssistant, device_tracker: str
) -> tuple[float, float] | None:
    """Extract longitude and latitude from a device tracker."""
    entity = hass.states.get(device_tracker)
    if entity is None:
        return None

    latitude = entity.attributes.get("latitude")
    if not latitude:
        LOGGER.warning(
            "Failed to find attribute 'latitude' in device_tracker %s", entity
        )
        return None

    longitude = entity.attributes.get("longitude")
    if not longitude:
        LOGGER.warning(
            "Failed to find attribute 'longitude' in device_tracker %s", entity
        )
        return None

    return (latitude, longitude)
