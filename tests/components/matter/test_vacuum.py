"""Test Matter vacuum."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    # test start action (from idle state)
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
        command=clusters.RvcRunMode.Commands.ChangeToMode(newMode=1),
    )
    matter_client.send_device_command.reset_mock()

    # test resume action (from paused state)
    # first set the operational state to paused
    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

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
        command=clusters.RvcOperationalState.Commands.Pause(),
    )
    matter_client.send_device_command.reset_mock()

    # test stop action
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
        command=clusters.RvcRunMode.Commands.ChangeToMode(newMode=0),
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

    # confirm state is 'idle' by setting the operational state to 0x01 (running) but mode is idle
    set_node_attribute(matter_node, 1, 97, 4, 0x01)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "idle"

    # confirm state is 'idle' by setting the operational state to 0x01 (running) but mode is cleaning
    set_node_attribute(matter_node, 1, 97, 4, 0x01)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "idle"

    # confirm state is 'paused' by setting the operational state to 0x02
    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "paused"

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

    # confirm state is 'cleaning' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has mapping tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "cleaning"

    # confirm state is 'unknown' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has neither cleaning or idle tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 5)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    # confirm state is 'error' by setting;
    # - the operational state to 0x03
    set_node_attribute(matter_node, 1, 97, 4, 3)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "error"


@pytest.mark.parametrize("node_fixture", ["vacuum_cleaner"])
async def test_vacuum_actions_no_supported_run_modes(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum entity actions when no supported run modes are available."""
    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    # Set empty supported modes to simulate no available run modes
    # RvcRunMode cluster ID is 84, SupportedModes attribute ID is 0
    set_node_attribute(matter_node, 1, 84, 0, [])
    # RvcOperationalState cluster ID is 97, AcceptedCommandList attribute ID is 65529
    set_node_attribute(matter_node, 1, 97, 65529, [])
    await trigger_subscription_callback(hass, matter_client)

    # test start action fails when no supported run modes
    with pytest.raises(
        HomeAssistantError,
        match="No supported run mode found to start the vacuum cleaner",
    ):
        await hass.services.async_call(
            "vacuum",
            "start",
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )

    # test stop action fails when no supported run modes
    with pytest.raises(
        HomeAssistantError,
        match="No supported run mode found to stop the vacuum cleaner",
    ):
        await hass.services.async_call(
            "vacuum",
            "stop",
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )

    # Ensure no commands were sent to the device
    assert matter_client.send_device_command.call_count == 0
