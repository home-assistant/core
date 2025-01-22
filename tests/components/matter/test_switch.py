"""Test Matter switches."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
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
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switches."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.SWITCH)


@pytest.mark.parametrize("node_fixture", ["on_off_plugin_unit"])
async def test_turn_on(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning on a switch."""
    state = hass.states.get("switch.mock_onoffpluginunit")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {
            "entity_id": "switch.mock_onoffpluginunit",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.On(),
    )

    set_node_attribute(matter_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("switch.mock_onoffpluginunit")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["on_off_plugin_unit"])
async def test_turn_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning off a switch."""
    state = hass.states.get("switch.mock_onoffpluginunit")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {
            "entity_id": "switch.mock_onoffpluginunit",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.Off(),
    )


@pytest.mark.parametrize("node_fixture", ["switch_unit"])
async def test_switch_unit(hass: HomeAssistant, matter_node: MatterNode) -> None:
    """Test if a switch entity is discovered from any (non-light) OnOf cluster device."""
    # A switch entity should be discovered as fallback for ANY Matter device (endpoint)
    # that has the OnOff cluster and does not fall into an explicit discovery schema
    # by another platform (e.g. light, lock etc.).
    state = hass.states.get("switch.mock_switchunit")
    assert state
    assert state.state == "off"
    assert state.attributes["friendly_name"] == "Mock SwitchUnit"


@pytest.mark.parametrize("node_fixture", ["room_airconditioner"])
async def test_power_switch(hass: HomeAssistant, matter_node: MatterNode) -> None:
    """Test if a Power switch entity is created for a device that supports that."""
    state = hass.states.get("switch.room_airconditioner_power")
    assert state
    assert state.state == "off"
    assert state.attributes["friendly_name"] == "Room AirConditioner Power"


@pytest.mark.parametrize("node_fixture", ["eve_thermo"])
async def test_numeric_switch(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test numeric switch entity is discovered and working using an Eve Thermo fixture ."""
    state = hass.states.get("switch.eve_thermo_child_lock")
    assert state
    assert state.state == "off"
    # name should be derived from description attribute
    assert state.attributes["friendly_name"] == "Eve Thermo Child lock"
    # test attribute changes
    set_node_attribute(matter_node, 1, 516, 1, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("switch.eve_thermo_child_lock")
    assert state.state == "on"
    set_node_attribute(matter_node, 1, 516, 1, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("switch.eve_thermo_child_lock")
    assert state.state == "off"
    # test switch service
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.eve_thermo_child_lock"},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.ThermostatUserInterfaceConfiguration.Attributes.KeypadLockout,
        ),
        value=1,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.eve_thermo_child_lock"},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.ThermostatUserInterfaceConfiguration.Attributes.KeypadLockout,
        ),
        value=0,
    )
