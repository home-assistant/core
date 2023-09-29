"""Test Matter Event entities."""
from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.core import HomeAssistant

from .common import setup_integration_with_node_fixture, trigger_subscription_callback


@pytest.fixture(name="generic_switch_node")
async def switch_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a GenericSwitch node."""
    return await setup_integration_with_node_fixture(
        hass, "generic-switch", matter_client
    )


@pytest.fixture(name="generic_switch_multi_node")
async def multi_switch_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a GenericSwitch node with multiple buttons."""
    return await setup_integration_with_node_fixture(
        hass, "generic-switch-multi", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_generic_switch_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    generic_switch_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node."""
    state = hass.states.get("event.mock_generic_switch")
    assert state
    assert state.state == "unknown"
    # the switch endpoint has no label so the entity name should be the device itself
    assert state.name == "Mock Generic Switch"
    # check event_types from featuremap 30
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "long_press",
        "long_release",
        "multi_press_ongoing",
        "multi_press_complete",
    ]
    # trigger firing a new event from the device
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=generic_switch_node.node_id,
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
    # trigger firing a multi press event
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=generic_switch_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=5,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"NewPosition": 3},
        ),
    )
    state = hass.states.get("event.mock_generic_switch")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_ongoing"
    assert state.attributes["NewPosition"] == 3


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_generic_switch_multi_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    generic_switch_multi_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node with multiple buttons."""
    state_button_1 = hass.states.get("event.mock_generic_switch_button_1")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # name should be 'DeviceName Button 1' due to the label set to just '1'
    assert state_button_1.name == "Mock Generic Switch Button 1"
    # check event_types from featuremap 14
    assert state_button_1.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "long_press",
        "long_release",
    ]
    # check button 2
    state_button_1 = hass.states.get("event.mock_generic_switch_fancy_button")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # name should be 'DeviceName Fancy Button' due to the label set to 'Fancy Button'
    assert state_button_1.name == "Mock Generic Switch Fancy Button"
