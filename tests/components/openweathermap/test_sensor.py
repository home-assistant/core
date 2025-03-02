"""Tests for OpenWeatherMap sensors."""

from pyopenweathermap import WeatherReport
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_V30,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import mock_config_entry, setup_platform
from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock, patch, snapshot_platform

# Define test data for mocked weather report
static_weather_report = _create_static_weather_report()


@pytest.mark.parametrize(
    ("mode", "patched_function", "mock_return"),
    [
        (
            OWM_MODE_FREE_CURRENT,
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
async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mode: str,
    patched_function: str,
    mock_return: WeatherReport,
) -> None:
    """Test sensor states are correctly collected from library with different modes and mocked function responses."""

    entry = mock_config_entry(mode)

    with patch(patched_function, new_callable=AsyncMock, return_value=mock_return):
        await setup_platform(hass, entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
