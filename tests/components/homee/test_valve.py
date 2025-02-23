"""Test Homee valves."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import (
    DOMAIN as VALVE_DOMAIN,
    SERVICE_SET_VALVE_POSITION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_valve_set_position(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set valve position service."""
    mock_homee.nodes = [build_mock_node("valve.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: "valve.test_valve_valve_position", "position": 100},
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 100)


async def test_valve_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the valve snapshots."""
    mock_homee.nodes = [build_mock_node("valve.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.VALVE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
