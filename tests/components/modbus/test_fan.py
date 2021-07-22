"""The tests for the Modbus fan component."""
from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_FANS,
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
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from .conftest import ReadResult, base_test, prepare_service_update

FAN_NAME = "test_fan"
ENTITY_ID = f"{FAN_DOMAIN}.{FAN_NAME}"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
                    CONF_ADDRESS: 1234,
                }
            ]
        },
        {
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
        {
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
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
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
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
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
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
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
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
async def test_config_fan(hass, mock_modbus):
    """Run configuration test for fan."""
    assert FAN_DOMAIN in hass.config.components


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
async def test_all_fan(hass, call_type, regs, verify, expected):
    """Run test for given config."""
    state = await base_test(
        hass,
        {
            CONF_NAME: FAN_NAME,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_WRITE_TYPE: call_type,
            **verify,
        },
        FAN_NAME,
        FAN_DOMAIN,
        CONF_FANS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "mock_test_state",
    [(State(ENTITY_ID, STATE_ON),)],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SCAN_INTERVAL: 0,
                }
            ]
        },
    ],
)
async def test_restore_state_fan(hass, mock_test_state, mock_modbus):
    """Run test for fan restore state."""
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_fan_service_turn(hass, caplog, mock_pymodbus):
    """Run test for service turn_on/turn_off."""

    ENTITY_ID2 = f"{FAN_DOMAIN}.{FAN_NAME}2"
    config = {
        MODBUS_DOMAIN: {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_FANS: [
                {
                    CONF_NAME: FAN_NAME,
                    CONF_ADDRESS: 17,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                },
                {
                    CONF_NAME: f"{FAN_NAME}2",
                    CONF_ADDRESS: 17,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_VERIFY: {},
                },
            ],
        },
    }
    assert await async_setup_component(hass, MODBUS_DOMAIN, config) is True
    await hass.async_block_till_done()
    assert MODBUS_DOMAIN in hass.config.components

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        "fan", "turn_on", service_data={"entity_id": ENTITY_ID}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    await hass.services.async_call(
        "fan", "turn_off", service_data={"entity_id": ENTITY_ID}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_pymodbus.read_holding_registers.return_value = ReadResult([0x01])
    assert hass.states.get(ENTITY_ID2).state == STATE_OFF
    await hass.services.async_call(
        "fan", "turn_on", service_data={"entity_id": ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_ON
    mock_pymodbus.read_holding_registers.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "fan", "turn_off", service_data={"entity_id": ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_OFF

    mock_pymodbus.write_register.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "fan", "turn_on", service_data={"entity_id": ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_UNAVAILABLE
    mock_pymodbus.write_coil.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "fan", "turn_off", service_data={"entity_id": ENTITY_ID}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_service_fan_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    config = {
        CONF_FANS: [
            {
                CONF_NAME: FAN_NAME,
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
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    mock_pymodbus.read_coils.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
