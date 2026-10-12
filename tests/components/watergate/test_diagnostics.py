"""Tests for the Watergate diagnostics."""

from collections.abc import Generator
import copy

from pytest_homeassistant.common import AsyncMock, MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from watergate_local_api.models import TelemetryData
from watergate_local_api.models.water_event import Event

from homeassistant.core import HomeAssistant

from . import init_integration
from .const import DEFAULT_DEVICE_STATE_V2


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics of a loaded config entry."""
    await init_integration(hass, mock_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))


async def test_diagnostics_ongoing_event(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test diagnostics include a water event that is in progress."""
    mock_watergate_client.async_get_telemetry_data.return_value = TelemetryData(
        1.5, 100, 28.32, Event(20, 30), []
    )
    await init_integration(hass, mock_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    assert result["data"]["telemetry"]["ongoing_event"] == {
        "volume": 20,
        "duration": 30,
    }


async def test_diagnostics_without_negative_water_meter(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test diagnostics of a device that reports no negative water meter."""
    state = copy.copy(DEFAULT_DEVICE_STATE_V2)
    state.water_meter_negative = None
    mock_watergate_client.async_get_device_state_v2.return_value = state
    await init_integration(hass, mock_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    assert result["data"]["state"]["water_meter_negative"] is None
    assert result["data"]["state"]["water_meter_positive"] == {
        "volume": 1.2,
        "duration": 100,
    }
