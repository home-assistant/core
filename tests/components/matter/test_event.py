"""Test Matter Event entities."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import snapshot_matter_entities, trigger_subscription_callback


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
    state = hass.states.get("event.mock_generic_switch")
    assert state
    assert state.state == "unknown"
    assert state.name == "Mock Generic Switch"
    # check event_types from featuremap 14 (0b1110)
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "long_press",
        "long_release",
    ]
    # trigger firing a new event from the device
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=1,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )
    state = hass.states.get("event.mock_generic_switch")
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch_multi"])
async def test_generic_switch_multi_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node with multiple buttons."""
    state_button_1 = hass.states.get("event.mock_generic_switch")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # check event_types from featuremap 30 (0b11110)
    assert state_button_1.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "multi_press_ongoing",
        "multi_press_complete",
        "long_press",
        "long_release",
    ]
    # check button 2
    state_button_2 = hass.states.get("event.mock_generic_switch_2")
    assert state_button_2
    assert state_button_2.state == "unknown"
    # check event_types from featuremap 30 (0b11110)
    assert state_button_2.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "multi_press_ongoing",
        "multi_press_complete",
        "long_press",
        "long_release",
    ]

    # trigger firing a multi press complete event
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=6,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"totalNumberOfPressesCounted": 2},
        ),
    )
    state = hass.states.get("event.mock_generic_switch")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_complete"
    assert state.attributes["press_count"] == 2
    assert state.attributes["event_type_extra"] == "double"


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch_multi"])
async def test_multi_press_event_entity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test MatterMultiPressEventEntity with press count data."""
    # Find the multi-press entity for endpoint 1 via entity registry
    entity_registry = er.async_get(hass)
    multi_press_entity_id = None
    for entry in entity_registry.entities.values():
        if (
            entry.platform == "matter"
            and "-1-MatterMultiPressSwitch-" in entry.unique_id
        ):
            multi_press_entity_id = entry.entity_id
            break
    assert multi_press_entity_id is not None, (
        "MatterMultiPressSwitch entity not found in registry"
    )

    # Verify event_types for the new entity (featuremap 30)
    state = hass.states.get(multi_press_entity_id)
    assert state
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "multi_press_ongoing",
        "multi_press_complete",
        "long_press",
        "long_release",
    ]

    # Test multi_press_ongoing with press_count and press_step (first event)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=5,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"currentNumberOfPressesCounted": 3},
        ),
    )
    state = hass.states.get(multi_press_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_ongoing"
    assert state.attributes["press_count"] == 3
    assert state.attributes["press_step"] == 3  # first event: 3 - 0

    # Test multi_press_ongoing sequence (press_step delta calculation)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=5,
            event_number=1,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"currentNumberOfPressesCounted": 5},
        ),
    )
    state = hass.states.get(multi_press_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_ongoing"
    assert state.attributes["press_count"] == 5
    assert state.attributes["press_step"] == 2  # 5 - 3

    # Test initial_press resets press_step tracking (previous was 5)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=1,
            event_number=2,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )
    state = hass.states.get(multi_press_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"

    # After reset, multi_press_ongoing calculates step from 0
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=5,
            event_number=3,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"currentNumberOfPressesCounted": 2},
        ),
    )
    state = hass.states.get(multi_press_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_ongoing"
    assert state.attributes["press_count"] == 2
    assert state.attributes["press_step"] == 2  # 2 - 0 (reset by initial_press)

    # Test multi_press_complete with press_count=2 (event_type_extra="double")
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=6,
            event_number=4,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"totalNumberOfPressesCounted": 2},
        ),
    )
    state = hass.states.get(multi_press_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_complete"
    assert state.attributes["press_count"] == 2
    assert state.attributes["event_type_extra"] == "double"

    # Test multi_press_complete with press_count=5 (no event_type_extra)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=6,
            event_number=5,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"totalNumberOfPressesCounted": 5},
        ),
    )
    state = hass.states.get(multi_press_entity_id)
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_complete"
    assert state.attributes["press_count"] == 5
    assert "event_type_extra" not in state.attributes


@pytest.mark.parametrize("node_fixture", ["mock_generic_switch_multi"])
async def test_deprecated_multi_press_entity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that deprecated MatterEventEntity is not created on new installs."""
    # On a new install (no pre-existing registry entry), the deprecated entity
    # should NOT be created. Only the new MatterMultiPressEventEntity should exist.
    entity_registry = er.async_get(hass)

    # Verify no deprecated entity (key="GenericSwitch") exists
    deprecated_entity_id = None
    for entry in entity_registry.entities.values():
        if (
            entry.platform == "matter"
            and "-1-GenericSwitch-" in entry.unique_id
        ):
            deprecated_entity_id = entry.entity_id
            break
    assert deprecated_entity_id is None, (
        "Deprecated GenericSwitch entity should not be created on new install"
    )

    # Verify the new entity IS created
    new_entity_id = None
    for entry in entity_registry.entities.values():
        if (
            entry.platform == "matter"
            and "-1-MatterMultiPressSwitch-" in entry.unique_id
        ):
            new_entity_id = entry.entity_id
            break
    assert new_entity_id is not None, (
        "New MatterMultiPressSwitch entity should be created"
    )
