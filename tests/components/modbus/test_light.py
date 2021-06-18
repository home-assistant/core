"""The tests for the Modbus light component."""
from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_INPUT_TYPE,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
    MODBUS_DOMAIN,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from .conftest import ReadResult, base_config_test, base_test, prepare_service_update

from tests.common import mock_restore_cache


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: "test_light",
                    CONF_ADDRESS: 1234,
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: "test_light",
                    CONF_ADDRESS: 1234,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: "test_light",
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: "test_light",
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: "test_light",
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: "test_light",
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: None,
                }
            ]
        },
    ],
)
async def test_config_light(hass, mock_modbus):
    """Run configuration test for light."""
    assert LIGHT_DOMAIN in hass.config.components


@pytest.mark.parametrize("call_type", [CALL_TYPE_COIL, CALL_TYPE_REGISTER_HOLDING])
@pytest.mark.parametrize(
    "regs,verify,expected",
    [
        (
            [0x00],
            {CONF_VERIFY: {}},
            STATE_OFF,
        ),
        (
            [0x01],
            {CONF_VERIFY: {}},
            STATE_ON,
        ),
        (
            [0xFE],
            {CONF_VERIFY: {}},
            STATE_OFF,
        ),
        (
            None,
            {CONF_VERIFY: {}},
            STATE_UNAVAILABLE,
        ),
        (
            None,
            {},
            STATE_OFF,
        ),
    ],
)
async def test_all_light(hass, call_type, regs, verify, expected):
    """Run test for given config."""
    light_name = "modbus_test_light"
    state = await base_test(
        hass,
        {
            CONF_NAME: light_name,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_WRITE_TYPE: call_type,
            **verify,
        },
        light_name,
        LIGHT_DOMAIN,
        CONF_LIGHTS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


async def test_restore_state_light(hass):
    """Run test for sensor restore state."""

    light_name = "test_light"
    entity_id = f"{LIGHT_DOMAIN}.{light_name}"
    test_value = STATE_ON
    config_light = {CONF_NAME: light_name, CONF_ADDRESS: 17}
    mock_restore_cache(
        hass,
        (State(f"{entity_id}", test_value),),
    )
    await base_config_test(
        hass,
        config_light,
        light_name,
        LIGHT_DOMAIN,
        CONF_LIGHTS,
        None,
        method_discovery=True,
    )
    assert hass.states.get(entity_id).state == test_value


async def test_light_service_turn(hass, caplog, mock_pymodbus):
    """Run test for service turn_on/turn_off."""

    entity_id1 = f"{LIGHT_DOMAIN}.light1"
    entity_id2 = f"{LIGHT_DOMAIN}.light2"
    config = {
        MODBUS_DOMAIN: {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_LIGHTS: [
                {
                    CONF_NAME: "light1",
                    CONF_ADDRESS: 17,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                },
                {
                    CONF_NAME: "light2",
                    CONF_ADDRESS: 17,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_VERIFY: {},
                },
            ],
        },
    }
    assert await async_setup_component(hass, MODBUS_DOMAIN, config) is True
    await hass.async_block_till_done()
    assert MODBUS_DOMAIN in hass.config.components

    assert hass.states.get(entity_id1).state == STATE_OFF
    await hass.services.async_call(
        "light", "turn_on", service_data={"entity_id": entity_id1}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id1).state == STATE_ON
    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity_id1}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id1).state == STATE_OFF

    mock_pymodbus.read_holding_registers.return_value = ReadResult([0x01])
    assert hass.states.get(entity_id2).state == STATE_OFF
    await hass.services.async_call(
        "light", "turn_on", service_data={"entity_id": entity_id2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id2).state == STATE_ON
    mock_pymodbus.read_holding_registers.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity_id2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id2).state == STATE_OFF

    mock_pymodbus.write_register.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "light", "turn_on", service_data={"entity_id": entity_id2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id2).state == STATE_UNAVAILABLE
    mock_pymodbus.write_coil.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity_id1}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id1).state == STATE_UNAVAILABLE


async def test_service_light_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    entity_id = "light.test"
    config = {
        CONF_LIGHTS: [
            {
                CONF_NAME: "test",
                CONF_ADDRESS: 1234,
                CONF_WRITE_TYPE: CALL_TYPE_COIL,
                CONF_VERIFY: {},
            }
        ]
    }
    mock_pymodbus.read_discrete_inputs.return_value = ReadResult([0x01])
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
    mock_pymodbus.read_coils.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF
