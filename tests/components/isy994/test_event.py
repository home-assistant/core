"""Test the ISY994 event platform."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

from pyisy.constants import (
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
)
from pyisy.helpers import NodeProperty
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_event_platform() -> Generator[None]:
    """Mock the platforms to only include event."""
    with patch("homeassistant.components.isy994.PLATFORMS", [Platform.EVENT]):
        yield


def _make_button_nodes(
    mock_isy: MagicMock, mock_node: Callable[..., Any]
) -> list[tuple[str, MagicMock]]:
    """Build a representative set of button-emitting Insteon nodes."""
    nodes: list[tuple[str, MagicMock]] = []

    # Primary loads — enabled by default
    primary = mock_node(
        mock_isy, "11 11 11 1", "Living Room Switch", "DimmerLampSwitch_ADV"
    )
    nodes.append(("Living Room Switch", primary))

    relay = mock_node(mock_isy, "22 22 22 1", "Garage Relay", "RelayLampSwitch_ADV")
    nodes.append(("Garage Relay", relay))

    keypad_load = mock_node(
        mock_isy, "33 33 33 1", "Hallway Keypad", "KeypadDimmer_ADV"
    )
    nodes.append(("Hallway Keypad", keypad_load))

    # Secondary keypad button — disabled by default
    sub_button = mock_node(
        mock_isy, "33 33 33 2", "Hallway Keypad B", "KeypadButton_ADV"
    )
    sub_button.parent_node = keypad_load
    sub_button.primary_node = "33 33 33 1"
    nodes.append(("Hallway Keypad B", sub_button))

    return nodes


async def test_event_entity_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Snapshot the event entities created for supported Insteon nodes."""
    mock_config_entry.add_to_hass(hass)
    mock_isy.nodes.__iter__.return_value = _make_button_nodes(mock_isy, mock_node)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entry in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        if entry.disabled_by:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("control", "expected_event_type"),
    [
        (CMD_ON, "on"),
        (CMD_OFF, "off"),
        (CMD_ON_FAST, "fast_on"),
        (CMD_OFF_FAST, "fast_off"),
        (CMD_FADE_UP, "fade_up"),
        (CMD_FADE_DOWN, "fade_down"),
        (CMD_FADE_STOP, "fade_stop"),
    ],
)
async def test_control_event_triggers_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    control: str,
    expected_event_type: str,
) -> None:
    """Control events from pyisy translate into event entity event_type updates."""
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Test Switch", "DimmerLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Test Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    handler = node.control_events.subscribe.call_args.args[0]
    handler(MagicMock(spec=NodeProperty, control=control))
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(Platform.EVENT)
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.attributes["event_type"] == expected_event_type


async def test_unsupported_control_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Control events not in the mapping must not trigger the entity."""
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Test Switch", "DimmerLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Test Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    handler = node.control_events.subscribe.call_args.args[0]
    handler(MagicMock(spec=NodeProperty, control="ST"))
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(Platform.EVENT)
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.attributes.get("event_type") is None
