"""The sensor tests for the AEMET OpenData platform."""

from unittest.mock import patch

from homeassistant.components.aemet.const import ATTRIBUTION
from homeassistant.components.weather import (
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_SNOWY,
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.const import ATTR_ATTRIBUTION
import homeassistant.util.dt as dt_util

from .util import async_init_integration


async def test_aemet_weather(hass):
    """Test states of the weather."""

    hass.config.set_time_zone("UTC")
    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ):
        await async_init_integration(hass)

    state = hass.states.get("weather.aemet_daily")
    assert state
    assert state.state == ATTR_CONDITION_SNOWY
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 99.0
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1004.4  # 100440.0 Pa -> hPa
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == -0.7
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 90.0
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 15.0  # 4.17 m/s -> km/h
    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == ATTR_CONDITION_PARTLYCLOUDY
    assert forecast.get(ATTR_FORECAST_PRECIPITATION) is None
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 30
    assert forecast.get(ATTR_FORECAST_TEMP) == 4
    assert forecast.get(ATTR_FORECAST_TEMP_LOW) == -4
    assert (
        forecast.get(ATTR_FORECAST_TIME)
        == dt_util.parse_datetime("2021-01-10 00:00:00+00:00").isoformat()
    )
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == 45.0
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 20.0  # 5.56 m/s -> km/h

    state = hass.states.get("weather.aemet_hourly")
    assert state is None
