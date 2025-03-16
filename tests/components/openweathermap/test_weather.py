"""Test the OpenWeatherMap weather entity."""

from pyopenweathermap import WeatherReport
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    DOMAIN,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
)
from homeassistant.components.openweathermap.weather import SERVICE_GET_MINUTE_FORECAST
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import mock_config_entry, setup_platform
from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock, MockConfigEntry, patch, snapshot_platform

ENTITY_ID = "weather.openweathermap"

# Define test data for mocked weather report
static_weather_report = _create_static_weather_report()


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


@pytest.mark.parametrize(
    ("mode", "patched_function", "mock_return"),
    [
        (
            OWM_MODE_FREE_CURRENT,
            "pyopenweathermap.client.free_client.OWMFreeClient.get_weather",
            static_weather_report,
        ),
        (
            OWM_MODE_FREE_FORECAST,
            "pyopenweathermap.client.free_client.OWMFreeClient.get_weather",
            static_weather_report,
        ),
        (
            OWM_MODE_V30,
            "pyopenweathermap.client.onecall_client.OWMOneCallClient.get_weather",
            static_weather_report,
        ),
    ],
)
async def test_weather_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mode: str,
    patched_function: str,
    mock_return: WeatherReport,
) -> None:
    """Test weather states are correctly collected from library with different modes and mocked function responses."""

    entry = mock_config_entry(mode)

    with patch(patched_function, new_callable=AsyncMock, return_value=mock_return):
        await setup_platform(hass, entry, [Platform.WEATHER])

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
