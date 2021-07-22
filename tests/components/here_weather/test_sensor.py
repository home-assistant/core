"""Tests for the here_weather sensor platform."""
from datetime import timedelta
from unittest.mock import patch

import herepy

from homeassistant.components.here_weather.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from . import mock_weather_for_coordinates

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_invalid_request(hass):
    """Test that sensor value is unavailable after an invalid request."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        with patch(
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            side_effect=mock_weather_for_coordinates,
        ):
            entry = MockConfigEntry(
                domain=DOMAIN,
                data={
                    CONF_API_KEY: "test",
                    CONF_NAME: DOMAIN,
                    CONF_LATITUDE: "40.79962",
                    CONF_LONGITUDE: "-73.970314",
                },
            )
            entry.add_to_hass(hass)

            registry = await hass.helpers.entity_registry.async_get_registry()

            # Pre-create registry entries for disabled by default sensors
            registry.async_get_or_create(
                "sensor",
                DOMAIN,
                "40.79962_-73.970314_forecast_7days_simple_windspeed_0",
                suggested_object_id="here_weather_forecast_7days_simple_windspeed_0",
                disabled_by=None,
            )

            await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()

            sensor = hass.states.get(
                "sensor.here_weather_forecast_7days_simple_windspeed_0"
            )
            assert sensor.state == "12.03"
        with patch(
            "herepy.DestinationWeatherApi.weather_for_coordinates",
            side_effect=herepy.InvalidRequestError("Invalid"),
        ):
            async_fire_time_changed(hass, utcnow + timedelta(DEFAULT_SCAN_INTERVAL * 2))
            await hass.async_block_till_done()
            sensor = hass.states.get(
                "sensor.here_weather_forecast_7days_simple_windspeed_0"
            )
            assert sensor.state == "unavailable"


async def test_forecast_astronomy(hass):
    """Test that forecast_astronomy works."""
    # Patching 'utcnow' to gain more control over the timed update.
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=mock_weather_for_coordinates,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
        )
        entry.add_to_hass(hass)

        registry = await hass.helpers.entity_registry.async_get_registry()

        # Pre-create registry entries for disabled by default sensors
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "40.79962_-73.970314_forecast_astronomy_sunrise_0",
            suggested_object_id="here_weather_forecast_astronomy_sunrise_0",
            disabled_by=None,
        )

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.here_weather_forecast_astronomy_sunrise_0")
        assert sensor.state == "6:55AM"


async def test_imperial(hass):
    """Test that imperial mode works."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=mock_weather_for_coordinates,
    ):
        hass.config.units = IMPERIAL_SYSTEM
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "test",
                CONF_NAME: DOMAIN,
                CONF_LATITUDE: "40.79962",
                CONF_LONGITUDE: "-73.970314",
            },
            options={
                CONF_SCAN_INTERVAL: 60,
            },
        )
        entry.add_to_hass(hass)

        registry = await hass.helpers.entity_registry.async_get_registry()

        # Pre-create registry entries for disabled by default sensors
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "40.79962_-73.970314_forecast_7days_simple_windspeed_0",
            suggested_object_id="here_weather_forecast_7days_simple_windspeed_0",
            disabled_by=None,
        )

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        sensor = hass.states.get(
            "sensor.here_weather_forecast_7days_simple_windspeed_0"
        )
        assert sensor.attributes.get("unit_of_measurement") == "mph"
