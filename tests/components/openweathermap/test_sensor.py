"""Tests for OpenWeatherMap sensors."""

from pyopenweathermap import WeatherReport
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import mock_config_entry
from .test_config_flow import _create_static_weather_report

from tests.common import AsyncMock, patch

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
    entry.add_to_hass(hass)

    with patch(patched_function, new_callable=AsyncMock, return_value=mock_return):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-{mode}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-{mode}-state"
        )
