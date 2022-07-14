"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import (
    ATTR_FORECAST,
    ATTR_FORECAST_DAILY,
    ATTR_FORECAST_HOURLY,
    ATTR_FORECAST_TWICE_DAILY,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude (often large) forecasts from being recorded in the database."""
    return {
        ATTR_FORECAST,
        ATTR_FORECAST_DAILY,
        ATTR_FORECAST_TWICE_DAILY,
        ATTR_FORECAST_HOURLY,
    }
