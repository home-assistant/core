"""Tests for the Bosch SHC binary sensor platform."""

from unittest.mock import MagicMock, patch

from boschshcpy import BatteryLevelService, ShutterContactService
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import make_device

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_setup_dependencies")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_device_helper: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all binary sensor entities."""
    mock_device_helper.shutter_contacts = [
        make_device(
            device_id="shutter-1",
            name="Front Door",
            device_class="ENTRANCE_DOOR",
            state=ShutterContactService.State.OPEN,
        )
    ]
    mock_device_helper.motion_detectors = [
        make_device(
            device_id="motion-1",
            name="Hallway Motion",
            batterylevel=BatteryLevelService.State.LOW_BATTERY,
        )
    ]

    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
