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
    ES_SYNCING,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import NodeChangedEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.isy994.const import EVENT_ISY994_CONTROL
from homeassistant.components.isy994.event import _sub_button_name
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_capture_events, snapshot_platform

SWITCH_ENTITY_ID = "switch.garage_relay"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up, overridden by parametrization."""
    return [Platform.EVENT]


@pytest.fixture(autouse=True)
def mock_event_platform(platforms: list[Platform]) -> Generator[None]:
    """Mock the platforms that are set up."""
    with patch("homeassistant.components.isy994.PLATFORMS", platforms):
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

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert any(entry.disabled_by is not None for entry in entries)

    for entry in entries:
        if entry.disabled_by:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("parent_name", "node_name", "expected"),
    [
        ("Hallway Keypad", "Hallway Keypad B", "B"),
        ("Hall", "Hallway B", "Hallway B"),  # prefix with no separator: unchanged
    ],
)
def test_sub_button_name_requires_separator(
    parent_name: str, node_name: str, expected: str
) -> None:
    """A parent name that is a bare prefix (no separator) must not be stripped.

    "Hall" is a prefix of "Hallway B" with no separator between them, so the
    sub-button label must stay "Hallway B" rather than being corrupted to
    "way B".
    """
    node = MagicMock()
    node.parent_node.name = parent_name
    node.name = node_name
    assert _sub_button_name(node) == expected


@pytest.mark.parametrize(
    ("control", "expected_event_type", "expected_direction", "expected_count"),
    [
        (CMD_ON, "press_end", "up", None),
        (CMD_OFF, "press_end", "down", None),
        (CMD_ON_FAST, "multi_press_end", "up", 2),
        (CMD_OFF_FAST, "multi_press_end", "down", 2),
        (CMD_FADE_UP, "long_press_start", "up", None),
        (CMD_FADE_DOWN, "long_press_start", "down", None),
    ],
)
async def test_control_event_triggers_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    control: str,
    expected_event_type: str,
    expected_direction: str,
    expected_count: int | None,
) -> None:
    """Control events from pyisy translate into the standard button event types."""
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Test Switch", "DimmerLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Test Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    handler = node.control_events.subscribe.call_args.args[0]
    handler(MagicMock(spec=NodeProperty, control=control))
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("event")
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.attributes["event_type"] == expected_event_type
    assert state.attributes.get("direction") == expected_direction
    assert state.attributes.get("multi_press_count") == expected_count


@pytest.mark.parametrize(
    ("controls", "expected_direction"),
    [
        pytest.param([CMD_FADE_DOWN, CMD_FADE_STOP], "down", id="paired_stop"),
        pytest.param([CMD_FADE_STOP], None, id="orphan_stop"),
        pytest.param(
            [CMD_FADE_DOWN, CMD_FADE_STOP, CMD_FADE_STOP], None, id="duplicate_stop"
        ),
    ],
)
async def test_fade_stop_direction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    controls: list[str],
    expected_direction: str | None,
) -> None:
    """CMD_FADE_STOP reports the direction of the fade it ends, once.

    The remembered direction is consumed by the stop that uses it, so a stop
    with no preceding fade start reports no direction instead of a stale one.
    """
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Test Switch", "DimmerLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Test Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    handler = node.control_events.subscribe.call_args.args[0]
    for control in controls:
        handler(MagicMock(spec=NodeProperty, control=control))
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("event")
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.attributes["event_type"] == "long_press_end"
    assert state.attributes.get("direction") == expected_direction
    # An unknown direction omits the attribute entirely rather than
    # publishing it as null.
    assert ("direction" in state.attributes) is (expected_direction is not None)


async def test_disabling_node_marks_entity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Availability tracks the node's enabled flag.

    The entity skips the base class's status_events subscription, so only the
    filtered enabled/disabled subscription keeps `available` current.
    """
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Test Switch", "DimmerLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Test Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = hass.states.async_entity_ids("event")[0]
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    node.enabled = False
    handler = mock_isy.nodes.status_events.subscribe.call_args.args[0]
    handler(MagicMock(spec=NodeChangedEvent), "key")
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_control_event_suppressed_while_websocket_syncing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Control events are dropped while the websocket replays status on connect.

    Without this guard, PyISY's post-connect status replay fires stale
    button events on every startup, config-entry reload, and reconnect.
    """
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Test Switch", "DimmerLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Test Switch", node)]
    mock_isy.websocket.status = ES_SYNCING

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    handler = node.control_events.subscribe.call_args.args[0]
    handler(MagicMock(spec=NodeProperty, control=CMD_ON))
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("event")
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.attributes.get("event_type") is None


@pytest.mark.parametrize("platforms", [[Platform.EVENT, Platform.SWITCH]])
@pytest.mark.parametrize(
    "control", [CMD_ON, CMD_OFF, CMD_ON_FAST, CMD_OFF_FAST, CMD_FADE_UP, CMD_FADE_STOP]
)
async def test_legacy_control_bus_event_not_duplicated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    control: str,
) -> None:
    """The legacy isy994_control bus event still fires exactly once per control.

    The node's primary (switch) entity keeps firing the bus event from the
    base class, while the event entity overrides async_on_control and must
    not fire a second one for the same control.
    """
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "22 22 22 1", "Garage Relay", "RelayLampSwitch_ADV")
    mock_isy.nodes.__iter__.return_value = [("Garage Relay", node)]
    events = async_capture_events(hass, EVENT_ISY994_CONTROL)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY_ID) is not None
    assert len(hass.states.async_entity_ids("event")) == 1

    for call in node.control_events.subscribe.call_args_list:
        call.args[0](MagicMock(spec=NodeProperty, control=control))
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["entity_id"] == SWITCH_ENTITY_ID
    assert events[0].data["control"] == control


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

    entity_ids = hass.states.async_entity_ids("event")
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.attributes.get("event_type") is None


@pytest.mark.parametrize(
    ("node_type", "expect_event_entity"),
    [
        ("1.14.1", True),  # SwitchLinc prefix from FILTER_INSTEON_TYPE
        ("2.44.1", True),  # KeypadLinc dimmer prefix from FILTER_INSTEON_TYPE
        ("3.32.1", True),  # BallastLinc prefix from FILTER_INSTEON_TYPE
        ("1.20.1", False),  # Not in FILTER_INSTEON_TYPE
    ],
)
async def test_legacy_insteon_type_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    node_type: str,
    expect_event_entity: bool,
) -> None:
    """Pre-5.0-firmware nodes with no node_def_id fall back to type-prefix matching."""
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "11 11 11 1", "Legacy Switch", None, node_type=node_type)
    mock_isy.nodes.__iter__.return_value = [("Legacy Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("event")
    assert (len(entity_ids) == 1) is expect_event_entity


async def test_event_entity_created_despite_sensor_string_override(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """A node forced into Platform.SENSOR by the sensor_string option still gets its event entity.

    Platform.EVENT is a parallel classification, not exclusive with the
    user's sensor_string override -- a SwitchLinc/KeypadLinc whose name
    happens to contain the (default "sensor") override string must still be
    matched against NODE_PARALLEL_PLATFORMS.
    """
    mock_config_entry.add_to_hass(hass)
    node = mock_node(
        mock_isy, "11 11 11 1", "Garage sensor Switch", "DimmerLampSwitch_ADV"
    )
    mock_isy.nodes.__iter__.return_value = [("Garage sensor Switch", node)]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("event")) == 1
