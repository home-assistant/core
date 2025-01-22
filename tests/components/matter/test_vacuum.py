"""Test Matter vacuum."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_vacuum(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the correct entities get created for a vacuum device."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.VACUUM)


@pytest.mark.parametrize("node_fixture", ["vacuum_cleaner"])
async def test_vacuum_actions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum entity actions."""
    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    # test return_to_base action
    await hass.services.async_call(
        "vacuum",
        "return_to_base",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcOperationalState.Commands.GoHome(),
    )
    matter_client.send_device_command.reset_mock()

    # test start/resume action
    await hass.services.async_call(
        "vacuum",
        "start",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcOperationalState.Commands.Resume(),
    )
    matter_client.send_device_command.reset_mock()

    # test pause action
    await hass.services.async_call(
        "vacuum",
        "pause",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OperationalState.Commands.Pause(),
    )
    matter_client.send_device_command.reset_mock()

    # test stop action
    # stop command is not supported by the vacuum fixture
    with pytest.raises(
        ServiceNotSupported,
        match="Entity vacuum.mock_vacuum does not support action vacuum.stop",
    ):
        await hass.services.async_call(
            "vacuum",
            "stop",
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )

    # update accepted command list to add support for stop command
    set_node_attribute(
        matter_node, 1, 97, 65529, [clusters.OperationalState.Commands.Stop.command_id]
    )
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "vacuum",
        "stop",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OperationalState.Commands.Stop(),
    )
    matter_client.send_device_command.reset_mock()


@pytest.mark.parametrize("node_fixture", ["vacuum_cleaner"])
async def test_vacuum_updates(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum entity updates."""
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state
    # confirm initial state is idle (as stored in the fixture)
    assert state.state == "idle"

    # confirm state is 'docked' by setting the operational state to 0x42
    set_node_attribute(matter_node, 1, 97, 4, 0x42)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "docked"

    # confirm state is 'docked' by setting the operational state to 0x41
    set_node_attribute(matter_node, 1, 97, 4, 0x41)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "docked"

    # confirm state is 'returning' by setting the operational state to 0x40
    set_node_attribute(matter_node, 1, 97, 4, 0x40)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "returning"

    # confirm state is 'error' by setting the operational state to 0x01
    set_node_attribute(matter_node, 1, 97, 4, 0x01)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "error"

    # confirm state is 'error' by setting the operational state to 0x02
    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "error"

    # confirm state is 'cleaning' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has cleaning tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "cleaning"

    # confirm state is 'idle' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has idle tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "idle"

    # confirm state is 'unknown' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has neither cleaning or idle tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"
