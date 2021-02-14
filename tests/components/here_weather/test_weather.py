"""Tests for the here_weather weather platform."""
from unittest.mock import patch

import herepy

from homeassistant.components.here_weather.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from . import mock_weather_for_coordinates

from tests.common import MockConfigEntry


async def test_weather(hass):
    """Test that weather has a value."""
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
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("weather.here_weather_forecast_7days_simple")
        assert sensor.state == "cloudy"


async def test_weather_no_response(hass):
    """Test that weather has a value."""
    with patch(
        "herepy.DestinationWeatherApi.weather_for_coordinates",
        side_effect=herepy.InvalidRequestError("Invalid"),
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
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("weather.here_weather_forecast_7days_simple")
        assert sensor.state == "unavailable"


async def test_weather_daily(hass):
    """Test that weather has a value."""
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
        )
        entry.add_to_hass(hass)

        registry = await hass.helpers.entity_registry.async_get_registry()

        # Pre-create registry entries for disabled by default sensors
        registry.async_get_or_create(
            "weather",
            DOMAIN,
            "here_weather_forecast_7days",
            suggested_object_id="here_weather_forecast_7days",
            disabled_by=None,
        )

        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("weather.here_weather_forecast_7days")
        assert sensor.state == "cloudy"
