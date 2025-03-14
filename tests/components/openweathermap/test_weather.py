"""Test the OpenWeatherMap weather entity."""

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    DEFAULT_LANGUAGE,
    DOMAIN,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_V30,
)
from homeassistant.components.openweathermap.weather import SERVICE_GET_MINUTE_FORECAST
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock, MockConfigEntry, patch

ENTITY_ID = "weather.openweathermap"
API_KEY = "test_api_key"
LATITUDE = 12.34
LONGITUDE = 56.78
NAME = "openweathermap"

# Define test data for mocked weather report
static_weather_report = _create_static_weather_report()


def mock_config_entry(mode: str) -> MockConfigEntry:
    """Create a mock OpenWeatherMap config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: API_KEY,
            CONF_LATITUDE: LATITUDE,
            CONF_LONGITUDE: LONGITUDE,
            CONF_NAME: NAME,
        },
        options={CONF_MODE: mode, CONF_LANGUAGE: DEFAULT_LANGUAGE},
        version=5,
    )


@pytest.fixture
def mock_config_entry_free_current() -> MockConfigEntry:
    """Create a mock OpenWeatherMap FREE_CURRENT config entry."""
    return mock_config_entry(OWM_MODE_FREE_CURRENT)


@pytest.fixture
def mock_config_entry_v30() -> MockConfigEntry:
    """Create a mock OpenWeatherMap v3.0 config entry."""
    return mock_config_entry(OWM_MODE_V30)


async def setup_mock_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Set up the MockConfigEntry and assert it is loaded correctly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID)
    assert mock_config_entry.state is ConfigEntryState.LOADED


@patch(
    "pyopenweathermap.client.onecall_client.OWMOneCallClient.get_weather",
    AsyncMock(return_value=static_weather_report),
)
async def test_get_minute_forecast(
    hass: HomeAssistant,
    mock_config_entry_v30: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_minute_forecast Service call."""
    await setup_mock_config_entry(hass, mock_config_entry_v30)

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MINUTE_FORECAST,
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert result == snapshot(name="mock_service_response")


@patch(
    "pyopenweathermap.client.free_client.OWMFreeClient.get_weather",
    AsyncMock(return_value=static_weather_report),
)
async def test_mode_fail(
    hass: HomeAssistant,
    mock_config_entry_free_current: MockConfigEntry,
) -> None:
    """Test that Minute forecasting fails when mode is not v3.0."""
    await setup_mock_config_entry(hass, mock_config_entry_free_current)

    # Expect a ServiceValidationError when mode is not OWM_MODE_V30
    with pytest.raises(
        ServiceValidationError,
        match="Minute forecast is available only when OpenWeatherMap mode is set to v3.0",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MINUTE_FORECAST,
            {"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )
