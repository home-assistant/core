"""Test WeatherKit data coordinator."""

from datetime import timedelta
from unittest.mock import patch

from apple_weatherkit.client import WeatherKitApiClientError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import init_integration, mock_weather_response

from tests.common import async_fire_time_changed


async def test_failed_updates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that we properly handle failed updates and recover from them."""
    with mock_weather_response():
        await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state != STATE_UNAVAILABLE

    initial_state = state.state

    # Expect stale data to be used before one hour

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
        side_effect=WeatherKitApiClientError,
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("weather.home")
    assert state
    assert state.state == initial_state

    # Expect state to be unavailable after one hour

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
        side_effect=WeatherKitApiClientError,
    ):
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("weather.home")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Expect state to be available if we can recover

    with mock_weather_response():
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("weather.home")
    assert state
    assert state.state != STATE_UNAVAILABLE
