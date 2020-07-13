"""Tests for the here_weather weather platform."""
import pytest

from homeassistant.components.here_weather.const import (
    CONF_API_KEY,
    DOMAIN,
    MODE_DAILY,
    MODE_DAILY_SIMPLE,
    MODE_HOURLY,
    MODE_OBSERVATION,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    EVENT_HOMEASSISTANT_START,
)

from .const import (
    daily_response,
    daily_simple_forecasts_response,
    hourly_response,
    observation_response,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "conf_mode, return_value",
    [
        (MODE_DAILY, daily_response),
        (MODE_DAILY_SIMPLE, daily_simple_forecasts_response),
        (MODE_OBSERVATION, observation_response),
        (MODE_HOURLY, hourly_response),
    ],
)
async def test_weather_imperial(hass, conf_mode, return_value):
    """Test that weather has a value."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=return_value,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_MODE: conf_mode,
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("weather.here_weather")
        assert sensor.state == "cloudy"
