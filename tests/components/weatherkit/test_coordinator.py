"""Test WeatherKit data coordinator."""

from datetime import timedelta
from unittest.mock import patch

from apple_weatherkit.client import WeatherKitApiClientError

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from . import init_integration

from tests.common import async_fire_time_changed


async def test_failed_updates(hass: HomeAssistant) -> None:
    """Test that we properly handle failed updates."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
        side_effect=WeatherKitApiClientError,
    ):
        async_fire_time_changed(
            hass,
            utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state = hass.states.get("weather.home")
    assert state
    assert state.state == STATE_UNAVAILABLE
