"""Test Matter locks."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="thermostat")
async def thermostat_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a thermostat node."""
    return await setup_integration_with_node_fixture(hass, "thermostat", matter_client)


@pytest.fixture(name="room_airconditioner")
async def room_airconditioner(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a room air conditioner node."""
    return await setup_integration_with_node_fixture(
        hass, "room-airconditioner", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_thermostat_base(
    hass: HomeAssistant,
    matter_client: MagicMock,
    thermostat: MatterNode,
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
    set_node_attribute(thermostat, 1, 513, 3, 1600)
    set_node_attribute(thermostat, 1, 513, 4, 3000)
    set_node_attribute(thermostat, 1, 513, 5, 1600)
    set_node_attribute(thermostat, 1, 513, 6, 3000)
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
    set_node_attribute(thermostat, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.OFF

    # test running state update from device
    set_node_attribute(thermostat, 1, 513, 41, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(thermostat, 1, 513, 41, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(thermostat, 1, 513, 41, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(thermostat, 1, 513, 41, 16)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(thermostat, 1, 513, 41, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(thermostat, 1, 513, 41, 32)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(thermostat, 1, 513, 41, 64)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(thermostat, 1, 513, 41, 66)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.OFF

    # change system mode to heat
    set_node_attribute(thermostat, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    # change occupied heating setpoint to 20
    set_node_attribute(thermostat, 1, 513, 18, 2000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["temperature"] == 20


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_thermostat_service_calls(
    hass: HomeAssistant,
    matter_client: MagicMock,
    thermostat: MatterNode,
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
        node_id=thermostat.node_id,
        attribute_path="1/513/17",
        value=2500,
    )
    matter_client.write_attribute.reset_mock()

    # ensure that no command is executed when the temperature is the same
    set_node_attribute(thermostat, 1, 513, 17, 2500)
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
    set_node_attribute(thermostat, 1, 513, 28, 4)
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
        node_id=thermostat.node_id,
        attribute_path="1/513/18",
        value=2000,
    )
    matter_client.write_attribute.reset_mock()

    # test dual setpoint temperature adjustments when heat_cool mode is active
    set_node_attribute(thermostat, 1, 513, 28, 1)
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
        node_id=thermostat.node_id,
        attribute_path="1/513/18",
        value=1000,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=thermostat.node_id,
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
        node_id=thermostat.node_id,
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
        node_id=thermostat.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=3,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=thermostat.node_id,
        attribute_path="1/513/17",
        value=2200,
    )
    matter_client.write_attribute.reset_mock()


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_room_airconditioner(
    hass: HomeAssistant,
    matter_client: MagicMock,
    room_airconditioner: MatterNode,
) -> None:
    """Test if a climate entity is created for a Room Airconditioner device."""
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.attributes["current_temperature"] == 20
    assert state.attributes["min_temp"] == 16
    assert state.attributes["max_temp"] == 32

    # test supported features correctly parsed
    # WITHOUT temperature_range support
    mask = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF
    assert state.attributes["supported_features"] & mask == mask

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
    set_node_attribute(room_airconditioner, 1, 513, 28, 7)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.FAN_ONLY

    # test dry hvac mode
    set_node_attribute(room_airconditioner, 1, 513, 28, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.DRY
