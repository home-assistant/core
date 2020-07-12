"""Tests for the here_weather weather platform."""
from homeassistant.components.here_weather.const import (
    CONF_API_KEY,
    DEFAULT_MODE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_START,
)
import homeassistant.util.dt as dt_util

from .const import daily_forecasts_response

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_weather(hass):
    """Test that sensor has a value."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=daily_forecasts_response,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_MODE: DEFAULT_MODE,
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
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
