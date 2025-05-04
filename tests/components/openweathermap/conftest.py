"""Configure tests for the OpenWeatherMap integration."""

import pytest

from homeassistant.components.openweathermap.const import DEFAULT_LANGUAGE, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)

from tests.common import MockConfigEntry

API_KEY = "test_api_key"
LATITUDE = 12.34
LONGITUDE = 56.78
NAME = "openweathermap"


@pytest.fixture
def mode(request: pytest.FixtureRequest) -> str:
    """Return mode passed in parameter."""
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
