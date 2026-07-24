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

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


async def trigger_switch_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    node: MatterNode,
    event_id: int,
    data: dict[str, Any] | None = None,
    endpoint_id: int = 1,
    cluster_id: int = 59,
) -> None:
    """Trigger a Switch cluster event on the given node."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=node.node_id,
            endpoint_id=endpoint_id,
            cluster_id=cluster_id,
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
    # event types are recomputed when the feature map changes,
    # here multi press support is added (featuremap 30)
    set_node_attribute(matter_node, 1, 59, 65532, 30)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/59/65532", 30)
    )
    state = hass.states.get("event.mock_generic_switch_button")
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "press_start",
        "press_end",
        "long_press_start",
        "long_press_end",
        "multi_press_ongoing",
        "multi_press_end",
    ]


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch"])
async def test_legacy_event_entity_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_node: MatterNode,
) -> None:
    """Test the legacy event entity is registered but disabled by default."""
    assert hass.states.get("event.mock_generic_switch_button_deprecated") is None
    entity_entry = entity_registry.async_get(
        "event.mock_generic_switch_button_deprecated"
    )
    assert entity_entry
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_entry.unique_id.endswith("-GenericSwitch-59-1")
    assert entity_entry.original_name == "Button (deprecated)"


@pytest.mark.parametrize(
    (
        "node_fixture",
        "entity_id",
        "expected_event_types",
        "event_id",
        "event_data",
        "expected_event_type",
    ),
    [
        pytest.param(
            "mock_generic_switch",
            "event.mock_generic_switch_button_deprecated",
            ["initial_press", "short_release", "long_press", "long_release"],
            1,
            None,
            "initial_press",
            id="momentary",
        ),
        pytest.param(
            "mock_generic_switch_multi",
            "event.mock_generic_switch_button_deprecated_1",
            ["multi_press_1", "multi_press_2", "long_press", "long_release"],
            6,
            {"totalNumberOfPressesCounted": 2},
            "multi_press_2",
            id="multi_press",
        ),
    ],
)
async def test_legacy_event_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    expected_event_types: list[str],
    event_id: int,
    event_data: dict[str, Any] | None,
    expected_event_type: str,
) -> None:
    """Test the legacy event entity still works when enabled."""
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    config_entry = hass.config_entries.async_entries("matter")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_EVENT_TYPES] == expected_event_types
    # trigger firing an event from the device
    await trigger_switch_event(hass, matter_client, matter_node, event_id, event_data)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type


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


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch"])
@pytest.mark.parametrize("attributes", [{"1/59/65532": 2}])
async def test_momentary_switch_without_release(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a momentary switch without release support."""
    state = hass.states.get("event.mock_generic_switch_button")
    assert state
    # a switch with featuremap 2 (0b10) only emits InitialPress,
    # which maps to press_end for single-event interactions
    assert state.attributes[ATTR_EVENT_TYPES] == ["press_end"]
    # trigger firing an InitialPress event from the device
    await trigger_switch_event(hass, matter_client, matter_node, 1)
    state = hass.states.get("event.mock_generic_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "press_end"


@pytest.mark.parametrize("node_fixture", ["mock_doorbell"])
@pytest.mark.parametrize(
    "attributes",
    [
        pytest.param({}, id="doorbell_only"),
        # an endpoint advertising the GenericSwitch device type alongside
        # Doorbell should not get the standard button event entity either
        pytest.param(
            {"1/29/0": [{"0": 328, "1": 1}, {"0": 15, "1": 1}]},
            id="doorbell_and_generic_switch",
        ),
    ],
)
async def test_doorbell_node(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_node: MatterNode,
) -> None:
    """Test a doorbell node only gets the legacy event entity for now."""
    # the Doorbell device type is excluded from the standard button event
    # entity, so it can get a dedicated doorbell event entity in the future
    assert hass.states.async_entity_ids("event") == []
    entity_entry = entity_registry.async_get("event.mock_doorbell_button_deprecated")
    assert entity_entry
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("node_fixture", ["mock_latching_switch"])
async def test_latching_switch_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a latching switch node."""
    state = hass.states.get("event.mock_latching_switch_button")
    assert state
    assert state.state == "unknown"
    # check event_types from featuremap 1 (0b1)
    assert state.attributes[ATTR_EVENT_TYPES] == ["switch_latched"]
    # trigger firing a SwitchLatched event from the device
    await trigger_switch_event(hass, matter_client, matter_node, 0, {"newPosition": 1})
    state = hass.states.get("event.mock_latching_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "switch_latched"
    assert state.attributes["newPosition"] == 1


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
    # an unknown event id from the device should be ignored
    await trigger_switch_event(hass, matter_client, matter_node, 7)
    state = hass.states.get("event.mock_action_switch_button")
    assert state.state == "unknown"
    # an event from another cluster should be ignored
    await trigger_switch_event(hass, matter_client, matter_node, 1, cluster_id=8)
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
