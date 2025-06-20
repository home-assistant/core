"""Helpers used for Met Office integration."""

from __future__ import annotations

import logging
from typing import Any, Literal

import datapoint
from datapoint.Forecast import Forecast
from requests import HTTPError

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER = logging.getLogger(__name__)


def fetch_data(
    connection: datapoint.Manager,
    latitude: float,
    longitude: float,
    frequency: Literal["daily", "twice-daily", "hourly"],
) -> Forecast:
    """Fetch weather and forecast from Datapoint API."""
    try:
        return connection.get_forecast(
            latitude, longitude, frequency, convert_weather_code=False
        )
    except (ValueError, datapoint.exceptions.APIException) as err:
        _LOGGER.error("Check Met Office connection: %s", err.args)
        raise UpdateFailed from err
    except HTTPError as err:
        if err.response.status_code == 401:
            raise ConfigEntryAuthFailed from err
        raise


def get_attribute(data: dict[str, Any] | None, attr_name: str) -> Any | None:
    """Get an attribute from weather data."""
    if data:
        return data.get(attr_name, {}).get("value")
    return None
