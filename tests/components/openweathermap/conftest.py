"""Configure tests for the OpenWeatherMap integration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.openweathermap.const import (
    DEFAULT_LANGUAGE,
    DOMAIN,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
    OWM_MODES,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock, MockConfigEntry

API_KEY = "test_api_key"
LATITUDE = 12.34
LONGITUDE = 56.78
NAME = "openweathermap"

# Define test data for mocked weather report
static_weather_report = _create_static_weather_report()


@pytest.fixture(params=OWM_MODES)
def mode(request: pytest.FixtureRequest) -> Generator[str]:
    """Return every mode."""
    return request.param


@pytest.fixture
def mock_config_entry(mode: str) -> MockConfigEntry:
    """Fixture for creating a mock OpenWeatherMap config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: API_KEY,
            CONF_LATITUDE: LATITUDE,
            CONF_LONGITUDE: LONGITUDE,
            CONF_NAME: NAME,
        },
        options={
            CONF_MODE: mode,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
        },
        entry_id="test",
        version=5,
    )


def get_weather(mode: str) -> str:
    """Return get_weather function."""
    if mode in (OWM_MODE_FREE_CURRENT, OWM_MODE_FREE_FORECAST):
        return "pyopenweathermap.client.free_client.OWMFreeClient.get_weather"
    if mode == OWM_MODE_V30:
        return "pyopenweathermap.client.onecall_client.OWMOneCallClient.get_weather"
    pytest.fail("Invalid mode")


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
):
    """Set up the OpenWeatherMap platform."""
    config_entry.add_to_hass(hass)
    mode = config_entry.options[CONF_MODE]
    with (
        patch("homeassistant.components.openweathermap.PLATFORMS", platforms),
        patch(
            get_weather(mode),
            new_callable=AsyncMock,
            return_value=static_weather_report,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
