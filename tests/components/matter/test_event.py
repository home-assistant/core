"""Test Matter Event entities."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy import SnapshotAssertion

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


@pytest.mark.parametrize("node_fixture", ["generic_switch"])
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
    # check event_types from featuremap 30
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
    state = hass.states.get("event.mock_generic_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"


@pytest.mark.parametrize("node_fixture", ["generic_switch_multi"])
async def test_generic_switch_multi_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node with multiple buttons."""
    state_button_1 = hass.states.get("event.mock_generic_switch_button_1")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # name should be 'DeviceName Button (1)' due to the label set to just '1'
    assert state_button_1.name == "Mock Generic Switch Button (1)"
    # check event_types from featuremap 14
    assert state_button_1.attributes[ATTR_EVENT_TYPES] == [
        "multi_press_1",
        "multi_press_2",
        "long_press",
        "long_release",
    ]
    # check button 2
    state_button_1 = hass.states.get("event.mock_generic_switch_fancy_button")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # name should be 'DeviceName Fancy Button' due to the label set to 'Fancy Button'
    assert state_button_1.name == "Mock Generic Switch Fancy Button"

    # trigger firing a multi press event
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
    state = hass.states.get("event.mock_generic_switch_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_2"
