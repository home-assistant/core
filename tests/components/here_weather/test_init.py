"""Tests for the here_weather integration."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.here_weather.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.util.dt as dt_util

from . import mock_weather_for_coordinates

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_number_of_listeners(hass):
    """Test that number_of_listerners works."""
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

            await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()

            sensor = hass.states.get("weather.here_weather_forecast_7days_simple")
            assert sensor.state == "cloudy"
            async_fire_time_changed(hass, utcnow + timedelta(DEFAULT_SCAN_INTERVAL * 2))
            await hass.async_block_till_done()
            sensor = hass.states.get("weather.here_weather_forecast_7days_simple")
            assert sensor.state == "cloudy"


async def test_update_interval(hass):
    """Test that update_interval is correctly set."""
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

            await hass.config_entries.async_setup(entry.entry_id)

            await hass.async_block_till_done()

            sensor = hass.states.get("weather.here_weather_forecast_7days_simple")
            assert sensor.state == "cloudy"
            with patch(
                "homeassistant.components.here_weather.active_here_clients",
                return_value=1000,
            ) as mock_active_here_clients:
                async_fire_time_changed(
                    hass, utcnow + timedelta(DEFAULT_SCAN_INTERVAL * 2)
                )
                await hass.async_block_till_done()
                assert len(mock_active_here_clients.mock_calls) == 1


async def test_unload_entry(hass):
    """Test unloading a config entry removes all entities."""
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN]
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not hass.data[DOMAIN]
