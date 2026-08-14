"""Test the Fressnapf Tracker device tracker platform."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from fressnapftracker import Tracker
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.fressnapf_tracker.PLATFORMS",
        [Platform.DEVICE_TRACKER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_auth_client")
async def test_device_tracker_no_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tracker_no_position: Tracker,
    mock_api_client_init: MagicMock,
) -> None:
    """Test device tracker is unavailable when position is None."""
    mock_config_entry.add_to_hass(hass)

    mock_api_client_init.get_tracker = AsyncMock(return_value=mock_tracker_no_position)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "device_tracker.fluffy"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "latitude" not in state.attributes
    assert "longitude" not in state.attributes
    assert "gps_accuracy" not in state.attributes
