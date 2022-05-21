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
    CONF_LAZY_ERROR,
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
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult

ENTITY_ID = f"{FAN_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
ENTITY_ID2 = f"{ENTITY_ID}_2"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                }
            ]
        },
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_LAZY_ERROR: 10,
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
                    CONF_NAME: TEST_ENTITY_NAME,
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
                    CONF_NAME: TEST_ENTITY_NAME,
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
                    CONF_NAME: TEST_ENTITY_NAME,
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


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                },
            ],
        },
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    "register_words,do_exception,config_addon,expected",
    [
        (
            [0x00],
            False,
            {CONF_VERIFY: {}},
            STATE_OFF,
        ),
        (
            [0x01],
            False,
            {CONF_VERIFY: {}},
            STATE_ON,
        ),
        (
            [0xFE],
            False,
            {CONF_VERIFY: {}},
            STATE_OFF,
        ),
        (
            [0x00],
            True,
            {CONF_VERIFY: {}},
            STATE_UNAVAILABLE,
        ),
        (
            [0x00],
            True,
            None,
            STATE_OFF,
        ),
    ],
)
async def test_all_fan(hass, mock_do_cycle, expected):
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


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
                    CONF_NAME: TEST_ENTITY_NAME,
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


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 17,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                },
                {
                    CONF_NAME: f"{TEST_ENTITY_NAME} 2",
                    CONF_ADDRESS: 18,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_VERIFY: {},
                },
            ],
        },
    ],
)
async def test_fan_service_turn(hass, caplog, mock_modbus):
    """Run test for service turn_on/turn_off."""

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

    mock_modbus.read_holding_registers.return_value = ReadResult([0x01])
    assert hass.states.get(ENTITY_ID2).state == STATE_OFF
    await hass.services.async_call(
        "fan", "turn_on", service_data={"entity_id": ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_ON
    mock_modbus.read_holding_registers.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "fan", "turn_off", service_data={"entity_id": ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_OFF

    mock_modbus.write_register.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "fan", "turn_on", service_data={"entity_id": ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_UNAVAILABLE
    mock_modbus.write_coil.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "fan", "turn_off", service_data={"entity_id": ENTITY_ID}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_FANS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                    CONF_VERIFY: {},
                }
            ]
        },
    ],
)
async def test_service_fan_update(hass, mock_modbus, mock_ha):
    """Run test for service homeassistant.update_entity."""
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_modbus.read_coils.return_value = ReadResult([0x01])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_no_discovery_info_fan(hass, caplog):
    """Test setup without discovery info."""
    assert FAN_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        FAN_DOMAIN,
        {FAN_DOMAIN: {"platform": MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert FAN_DOMAIN in hass.config.components
