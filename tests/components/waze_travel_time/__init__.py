"""Tests for the Waze Travel Time integration."""

from homeassistant.components.waze_travel_time.const import (
    CONF_BASE_COORDINATES,
    DEFAULT_OPTIONS,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant


def get_default_options(
    hass: HomeAssistant,
) -> dict[str, str | bool | list[str] | dict[str, int] | dict[str, float]]:
    """Return the default options for Waze Travel Time."""
    return {
        **DEFAULT_OPTIONS,
        CONF_BASE_COORDINATES: {
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
        },
    }
