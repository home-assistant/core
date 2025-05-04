"""Shared utilities for OpenWeatherMap tests."""

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock, MockConfigEntry

static_weather_report = _create_static_weather_report()


def _create_mocked_owm_factory() -> MagicMock:
    """Create a mocked OWM client."""
    mocked_owm_client = MagicMock()
    mocked_owm_client.get_weather = AsyncMock(return_value=static_weather_report)
    return mocked_owm_client


async def setup_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    platforms: list[Platform],
):
    """Set up the OpenWeatherMap platform."""
    owm_client_mock.return_value = _create_mocked_owm_factory()

    config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.openweathermap.PLATFORMS", platforms),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
