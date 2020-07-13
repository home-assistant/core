"""Tests for the here_weather sensor platform."""
from datetime import timedelta

import herepy

from homeassistant.components.here_weather.const import (
    ASTRONOMY_ATTRIBUTES,
    CONF_API_KEY,
    DEFAULT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODE_ASTRONOMY,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_START,
)
import homeassistant.util.dt as dt_util

from .const import astronomy_response, daily_simple_forecasts_response

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_invalid_request(hass):
    """Test that sensor value is unavailable after an invalid request."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        with patch(
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            return_value=daily_simple_forecasts_response,
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

            sensor = hass.states.get("sensor.here_weather_low_temperature")
            assert sensor.state == "-1.80"
        with patch(
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            side_effect=herepy.InvalidRequestError("Invalid"),
        ):
            async_fire_time_changed(hass, utcnow + timedelta(DEFAULT_SCAN_INTERVAL * 2))
            await hass.async_block_till_done()
            sensor = hass.states.get("sensor.here_weather_low_temperature")
            assert sensor.state == "unavailable"


async def test_forecast_astronomy(hass):
    """Test that forecast_astronomy works."""
    # Patching 'utcnow' to gain more control over the timed update.
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=astronomy_response,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_MODE: MODE_ASTRONOMY,
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

        sensor = hass.states.get("sensor.here_weather_sunrise")
        assert sensor.state == "6:55AM"
        assert len(hass.states.async_all()) == len(ASTRONOMY_ATTRIBUTES)


async def test_imperial(hass):
    """Test that imperial mode works."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        return_value=daily_simple_forecasts_response,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_MODE: DEFAULT_MODE,
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

        sensor = hass.states.get("sensor.here_weather_wind_speed")
        assert sensor.attributes.get("unit_of_measurement") == "mph"
