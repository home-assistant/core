"""Shared utilities for OpenWeatherMap tests."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock

static_weather_report = _create_static_weather_report()


async def setup_platform(hass: HomeAssistant, config_entry, platforms: list[Platform]):
    """Set up the OpenWeatherMap platform."""
    config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.openweathermap.PLATFORMS", platforms),
        patch(
            "homeassistant.components.openweathermap.coordinator.WeatherUpdateCoordinator._get_weather_report",
            new_callable=AsyncMock,
            return_value=static_weather_report,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
