"""Test homee events."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("entity_id", "attribute_id", "expected_event_types"),
    [
        (
            "event.remote_control_up_down_remote",
            1,
            [
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
            ],
        ),
        (
            "event.remote_control_switch_2",
            3,
            ["upper", "lower", "released"],
        ),
    ],
)
async def test_event_triggers(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    attribute_id: int,
    expected_event_types: list[str],
) -> None:
    """Test that the correct event fires when the attribute changes."""
    mock_homee.nodes = [build_mock_node("events.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    # Simulate the event triggers.
    attribute = mock_homee.nodes[0].attributes[attribute_id - 1]
    for i, event_type in enumerate(expected_event_types):
        attribute.current_value = i
        attribute.add_on_changed_listener.call_args_list[1][0][0](attribute)
        await hass.async_block_till_done()

        # Check if the event was fired
        state = hass.states.get(entity_id)
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
