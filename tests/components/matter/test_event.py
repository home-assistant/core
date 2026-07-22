"""Test Matter Event entities."""

from typing import Any
from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    ATTR_MULTI_PRESS_COUNT,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import snapshot_matter_entities, trigger_subscription_callback


async def trigger_switch_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    node: MatterNode,
    event_id: int,
    data: dict[str, Any] | None = None,
    endpoint_id: int = 1,
) -> None:
    """Trigger a Switch cluster event on the given node."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=node.node_id,
            endpoint_id=endpoint_id,
            cluster_id=59,
            event_id=event_id,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=data,
        ),
    )


@pytest.mark.usefixtures("matter_devices")
async def test_events(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test events."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.EVENT)


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch"])
async def test_generic_switch_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node."""
    state = hass.states.get("event.mock_generic_switch_button")
    assert state
    assert state.state == "unknown"
    assert state.name == "Mock Generic Switch Button"
    # check event_types from featuremap 14 (0b1110)
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "press_start",
        "press_end",
        "long_press_start",
        "long_press_end",
    ]
    # trigger firing an InitialPress event from the device
    await trigger_switch_event(hass, matter_client, matter_node, 1)
    state = hass.states.get("event.mock_generic_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "press_start"
    # trigger firing a ShortRelease event from the device
    await trigger_switch_event(hass, matter_client, matter_node, 3)
    state = hass.states.get("event.mock_generic_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "press_end"


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch"])
async def test_legacy_event_entity_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_node: MatterNode,
) -> None:
    """Test the legacy event entity is registered but disabled by default."""
    assert hass.states.get("event.mock_generic_switch_button_2") is None
    entity_entry = entity_registry.async_get("event.mock_generic_switch_button_2")
    assert entity_entry
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_entry.unique_id.endswith("-GenericSwitch-59-1")


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch_multi"])
async def test_legacy_event_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the legacy event entity still works when enabled."""
    entity_registry.async_update_entity(
        "event.mock_generic_switch_button_1_2", disabled_by=None
    )
    config_entry = hass.config_entries.async_entries("matter")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("event.mock_generic_switch_button_1_2")
    assert state
    # check event_types from featuremap 30 (0b11110) and MultiPressMax unset
    # (default 2)
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "multi_press_1",
        "multi_press_2",
        "long_press",
        "long_release",
    ]
    # trigger firing a MultiPressComplete event from the device
    await trigger_switch_event(
        hass, matter_client, matter_node, 6, {"totalNumberOfPressesCounted": 2}
    )
    state = hass.states.get("event.mock_generic_switch_button_1_2")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_2"


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch_multi"])
async def test_generic_switch_multi_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node with multiple buttons."""
    state_button_1 = hass.states.get("event.mock_generic_switch_button_1")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # name should be 'DeviceName Button (1)'
    assert state_button_1.name == "Mock Generic Switch Button (1)"
    # check event_types from featuremap 30 (0b11110)
    assert state_button_1.attributes[ATTR_EVENT_TYPES] == [
        "press_start",
        "press_end",
        "long_press_start",
        "long_press_end",
        "multi_press_ongoing",
        "multi_press_end",
    ]
    # check button 2
    state_button_2 = hass.states.get("event.mock_generic_switch_button_fancy_button")
    assert state_button_2
    assert state_button_2.state == "unknown"
    # name should be 'DeviceName Button (Fancy Button)' due to
    # ha_entitylabel 'Fancy Button'
    assert state_button_2.name == "Mock Generic Switch Button (Fancy Button)"

    # trigger firing a MultiPressOngoing event from the device
    await trigger_switch_event(
        hass, matter_client, matter_node, 5, {"currentNumberOfPressesCounted": 2}
    )
    state = hass.states.get("event.mock_generic_switch_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_ongoing"
    assert state.attributes[ATTR_MULTI_PRESS_COUNT] == 2

    # trigger firing a MultiPressComplete event from the device
    await trigger_switch_event(
        hass, matter_client, matter_node, 6, {"totalNumberOfPressesCounted": 3}
    )
    state = hass.states.get("event.mock_generic_switch_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_end"
    assert state.attributes[ATTR_MULTI_PRESS_COUNT] == 3


@pytest.mark.parametrize("node_fixture", ["mock_action_switch"])
async def test_action_switch_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for an action switch node."""
    state = hass.states.get("event.mock_action_switch_button")
    assert state
    assert state.state == "unknown"
    # check event_types from featuremap 58 (0b111010):
    # an action switch does not emit ShortRelease and MultiPressOngoing events
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "press_start",
        "long_press_start",
        "long_press_end",
        "multi_press_end",
    ]
    # a ShortRelease event from the device should be ignored
    await trigger_switch_event(hass, matter_client, matter_node, 3)
    state = hass.states.get("event.mock_action_switch_button")
    assert state.state == "unknown"
    # trigger firing a MultiPressComplete event from the device
    await trigger_switch_event(
        hass, matter_client, matter_node, 6, {"totalNumberOfPressesCounted": 4}
    )
    state = hass.states.get("event.mock_action_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_end"
    assert state.attributes[ATTR_MULTI_PRESS_COUNT] == 4


@pytest.mark.parametrize("node_fixture", ["ikea_scroll_wheel"])
@pytest.mark.parametrize(
    ("presses_counted", "multi_press_count"),
    [
        (11, 11),
        # a count of 0 means the sequence exceeded MultiPressMax (18)
        (0, 0),
    ],
    ids=["11_presses", "aborted_sequence"],
)
async def test_scroll_wheel_press_count(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    presses_counted: int,
    multi_press_count: int,
) -> None:
    """Test the press count is passed through uncapped for a scroll wheel."""
    state = hass.states.get("event.bilresa_scroll_wheel_button_1")
    assert state
    # check event_types from featuremap 22 (0b10110)
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "press_start",
        "press_end",
        "multi_press_ongoing",
        "multi_press_end",
    ]
    # trigger firing a MultiPressComplete event from the device
    await trigger_switch_event(
        hass,
        matter_client,
        matter_node,
        6,
        {"totalNumberOfPressesCounted": presses_counted},
    )
    state = hass.states.get("event.bilresa_scroll_wheel_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_end"
    assert state.attributes[ATTR_MULTI_PRESS_COUNT] == multi_press_count
