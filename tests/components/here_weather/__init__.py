"""Tests for here_weather component."""
import herepy

from homeassistant.components.here_weather.const import (
    MODE_ASTRONOMY,
    MODE_DAILY,
    MODE_DAILY_SIMPLE,
    MODE_HOURLY,
    MODE_OBSERVATION,
)

from .const import (
    astronomy_response,
    daily_response,
    daily_simple_forecasts_response,
    hourly_response,
    observation_response,
)


def mock_weather_for_coordinates(*args, **kwargs):
    """Return mock data for request weather product type."""
    if args[2] == herepy.WeatherProductType[MODE_ASTRONOMY]:
        return astronomy_response
    elif args[2] == herepy.WeatherProductType[MODE_HOURLY]:
        return hourly_response
    elif args[2] == herepy.WeatherProductType[MODE_DAILY]:
        return daily_response
    elif args[2] == herepy.WeatherProductType[MODE_DAILY_SIMPLE]:
        return daily_simple_forecasts_response
    elif args[2] == herepy.WeatherProductType[MODE_OBSERVATION]:
        return observation_response
