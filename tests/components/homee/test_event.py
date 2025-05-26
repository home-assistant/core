"""Test homee events."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_event_fires(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the correct event fires when the attribute changes."""

    EVENT_TYPES = [
        "released",
        "up",
        "down",
        "stop",
        "up_long",
        "down_long",
        "stop_long",
        "c_button",
        "b_button",
        "a_button",
    ]
    mock_homee.nodes = [build_mock_node("events.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    # Simulate the event triggers.
    attribute = mock_homee.nodes[0].attributes[0]
    for i, event_type in enumerate(EVENT_TYPES):
        attribute.current_value = i
        attribute.add_on_changed_listener.call_args_list[1][0][0](attribute)
        await hass.async_block_till_done()

        # Check if the event was fired
        state = hass.states.get("event.remote_control_up_down_remote")
        assert state.attributes[ATTR_EVENT_TYPE] == event_type


async def test_event_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the event entity snapshot."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.EVENT]):
        mock_homee.nodes = [build_mock_node("events.json")]
        mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
