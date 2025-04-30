"""Test Matter locks."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_climates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climates."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.CLIMATE)


@pytest.mark.parametrize("node_fixture", ["thermostat"])
async def test_thermostat_base(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat base attributes and state updates."""
    # test entity attributes
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 35
    assert state.attributes["temperature"] is None
    assert state.state == HVACMode.COOL

    # test supported features correctly parsed
    # including temperature_range support
    mask = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    assert state.attributes["supported_features"] & mask == mask

    # test common state updates from device
    set_node_attribute(matter_node, 1, 513, 3, 1600)
    set_node_attribute(matter_node, 1, 513, 4, 3000)
    set_node_attribute(matter_node, 1, 513, 5, 1600)
    set_node_attribute(matter_node, 1, 513, 6, 3000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 16
    assert state.attributes["max_temp"] == 30
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    ]

    # test system mode update from device
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.OFF

    # test running state update from device
    set_node_attribute(matter_node, 1, 513, 41, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 16)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 32)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 64)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 66)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.OFF

    # change system mode to heat
    set_node_attribute(matter_node, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    # change occupied heating setpoint to 20
    set_node_attribute(matter_node, 1, 513, 18, 2000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["temperature"] == 20


@pytest.mark.parametrize("node_fixture", ["thermostat"])
async def test_thermostat_service_calls(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test climate platform service calls."""
    # test single-setpoint temperature adjustment when cool mode is active
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.COOL
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2500,
    )
    matter_client.write_attribute.reset_mock()

    # ensure that no command is executed when the temperature is the same
    set_node_attribute(matter_node, 1, 513, 17, 2500)
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 0
    matter_client.write_attribute.reset_mock()

    # test single-setpoint temperature adjustment when heat mode is active
    set_node_attribute(matter_node, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 20,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=2000,
    )
    matter_client.write_attribute.reset_mock()

    # test dual setpoint temperature adjustments when heat_cool mode is active
    set_node_attribute(matter_node, 1, 513, 28, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 10,
            "target_temp_high": 30,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=1000,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=3000,
    )
    matter_client.write_attribute.reset_mock()

    # test change HAVC mode to heat
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            "entity_id": "climate.longan_link_hvac",
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=4,
    )
    matter_client.send_device_command.reset_mock()

    # change target_temp and hvac_mode in the same call
    matter_client.send_device_command.reset_mock()
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 22,
            "hvac_mode": HVACMode.COOL,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=3,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2200,
    )
    matter_client.write_attribute.reset_mock()


@pytest.mark.parametrize("node_fixture", ["room_airconditioner"])
async def test_room_airconditioner(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if a climate entity is created for a Room Airconditioner device."""
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.attributes["current_temperature"] == 20
    # room airconditioner has mains power on OnOff cluster with value set to False
    assert state.state == HVACMode.OFF

    # test supported features correctly parsed
    # WITHOUT temperature_range support
    mask = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF
    assert state.attributes["supported_features"] & mask == mask

    # set mains power to ON (OnOff cluster)
    set_node_attribute(matter_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")

    # test supported HVAC modes include fan and dry modes
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT_COOL,
    ]
    # test fan-only hvac mode
    set_node_attribute(matter_node, 1, 513, 28, 7)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.FAN_ONLY

    # test dry hvac mode
    set_node_attribute(matter_node, 1, 513, 28, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.DRY

    # test featuremap update
    set_node_attribute(matter_node, 1, 513, 65532, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state.attributes["supported_features"] & ClimateEntityFeature.TURN_ON


@pytest.mark.parametrize("node_fixture", ["silabs_refrigerator"])
async def test_temperature_control(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test TemperatureControl base attributes and state updates."""
    # test entity attributes
    state = hass.states.get("climate.refrigerator_temperature_control_2")
    assert state.state == HVACMode.COOL

    # test common state updates from refrigerator device (freezer cabinet)
    set_node_attribute(matter_node, 2, 86, 1, -1700)
    set_node_attribute(matter_node, 2, 86, 2, -1600)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.refrigerator_temperature_control_2")
    assert state
    assert state.attributes["min_temp"] == -17
    assert state.attributes["max_temp"] == -16

    # change target_temp
    matter_client.send_device_command.reset_mock()
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.refrigerator_temperature_control_2",
            "temperature": -17,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=2,
        command=clusters.TemperatureControl.Commands.SetTemperature(
            targetTemperature=-1700
        ),
    )
    matter_client.write_attribute.reset_mock()
