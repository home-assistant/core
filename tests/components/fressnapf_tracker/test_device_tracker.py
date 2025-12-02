"""Test the Fressnapf Tracker device tracker platform."""

from unittest.mock import AsyncMock, MagicMock

from fressnapftracker import Tracker
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"{device_entry.name}-entry"), (
            f"device entry snapshot failed for {device_entry.name}"
        )


@pytest.mark.usefixtures("mock_auth_client")
async def test_device_tracker_no_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tracker_no_position: Tracker,
    mock_api_client: MagicMock,
) -> None:
    """Test device tracker is unavailable when position is None."""
    mock_config_entry.add_to_hass(hass)

    mock_api_client.get_tracker = AsyncMock(return_value=mock_tracker_no_position)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "device_tracker.fluffy"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "latitude" not in state.attributes
    assert "longitude" not in state.attributes
    assert "gps_accuracy" not in state.attributes
