"""Test Matter valve."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_valves(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test valves."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.VALVE)


@pytest.mark.parametrize("node_fixture", ["valve"])
async def test_valve(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test valve entity is created for a Matter ValveConfigurationAndControl Cluster."""
    entity_id = "valve.valve_valve"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "closed"
    assert state.attributes["friendly_name"] == "Valve Valve"

    # test close_valve action
    await hass.services.async_call(
        "valve",
        "close_valve",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ValveConfigurationAndControl.Commands.Close(),
    )
    matter_client.send_device_command.reset_mock()

    # test open_valve action
    await hass.services.async_call(
        "valve",
        "open_valve",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ValveConfigurationAndControl.Commands.Open(),
    )
    matter_client.send_device_command.reset_mock()

    # set changing state to 'opening'
    set_node_attribute(matter_node, 1, 129, 4, 2)
    set_node_attribute(matter_node, 1, 129, 5, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "opening"

    # set changing state to 'closing'
    set_node_attribute(matter_node, 1, 129, 4, 2)
    set_node_attribute(matter_node, 1, 129, 5, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "closing"

    # set changing state to 'open'
    set_node_attribute(matter_node, 1, 129, 4, 1)
    set_node_attribute(matter_node, 1, 129, 5, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "open"

    # add support for setting position by updating the featuremap
    set_node_attribute(matter_node, 1, 129, 65532, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 0

    # update current position
    set_node_attribute(matter_node, 1, 129, 6, 50)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 50

    # test set_position action
    await hass.services.async_call(
        "valve",
        "set_valve_position",
        {
            "entity_id": entity_id,
            "position": 100,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ValveConfigurationAndControl.Commands.Open(targetLevel=100),
    )
    matter_client.send_device_command.reset_mock()
