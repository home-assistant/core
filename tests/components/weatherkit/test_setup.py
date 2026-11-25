"""Test the WeatherKit setup process."""

from unittest.mock import patch

from apple_weatherkit.client import (
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientError,
)
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.weatherkit.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import EXAMPLE_CONFIG_DATA


async def test_auth_error_handling(hass: HomeAssistant) -> None:
    """Test that we handle authentication errors at setup properly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data=EXAMPLE_CONFIG_DATA,
    )

    with (
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
            side_effect=WeatherKitApiClientAuthenticationError,
        ),
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
            side_effect=WeatherKitApiClientAuthenticationError,
        ),
    ):
        entry.add_to_hass(hass)
        setup_result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert setup_result is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        entry.reason == "Authentication error initializing the WeatherKit integration"
    )
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_client_error_handling(hass: HomeAssistant) -> None:
    """Test that we handle API client errors at setup properly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data=EXAMPLE_CONFIG_DATA,
    )

    with (
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
            side_effect=WeatherKitApiClientError,
        ),
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
            side_effect=WeatherKitApiClientError,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
