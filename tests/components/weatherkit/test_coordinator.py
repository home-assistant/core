"""Test WeatherKit data coordinator."""
from unittest.mock import patch

from apple_weatherkit.client import WeatherKitApiClientError
import pytest

from homeassistant.components.weatherkit.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import init_integration


async def test_failed_updates(hass: HomeAssistant) -> None:
    """Test that we properly handle failed updates."""
    entry = await init_integration(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    with pytest.raises(UpdateFailed), patch(
        "apple_weatherkit.client.WeatherKitApiClient.get_weather_data",
        side_effect=WeatherKitApiClientError,
    ):
        await coordinator._async_update_data()
