"""The tests for the Modbus sensor component."""
import logging

import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_PRECISION,
    CONF_REGISTERS,
    CONF_SCALE,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SLAVE,
    CONF_STRUCTURE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State

from .conftest import ReadResult, base_config_test, base_test, prepare_service_update

SENSOR_NAME = "test_sensor"
ENTITY_ID = f"{SENSOR_DOMAIN}.{SENSOR_NAME}"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_COUNT: 1,
                    CONF_DATA_TYPE: "int",
                    CONF_PRECISION: 0,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_DEVICE_CLASS: "battery",
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_COUNT: 1,
                    CONF_DATA_TYPE: "int",
                    CONF_PRECISION: 0,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                    CONF_DEVICE_CLASS: "battery",
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_COUNT: 1,
                    CONF_SWAP: CONF_SWAP_NONE,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_COUNT: 1,
                    CONF_SWAP: CONF_SWAP_BYTE,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_COUNT: 2,
                    CONF_SWAP: CONF_SWAP_WORD,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_COUNT: 2,
                    CONF_SWAP: CONF_SWAP_WORD_BYTE,
                }
            ]
        },
    ],
)
async def test_config_sensor(hass, mock_modbus):
    """Run configuration test for sensor."""
    assert SENSOR_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config,error_message",
    [
        (
            {
                CONF_ADDRESS: 1234,
                CONF_COUNT: 8,
                CONF_PRECISION: 2,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_STRUCTURE: ">no struct",
            },
            "bad char in struct format",
        ),
        (
            {
                CONF_ADDRESS: 1234,
                CONF_COUNT: 2,
                CONF_PRECISION: 2,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_STRUCTURE: ">4f",
            },
            "Structure request 16 bytes, but 2 registers have a size of 4 bytes",
        ),
        (
            {
                CONF_ADDRESS: 1234,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_COUNT: 4,
                CONF_SWAP: CONF_SWAP_NONE,
                CONF_STRUCTURE: "invalid",
            },
            "bad char in struct format",
        ),
        (
            {
                CONF_ADDRESS: 1234,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_COUNT: 4,
                CONF_SWAP: CONF_SWAP_NONE,
                CONF_STRUCTURE: "",
            },
            "Error in sensor test_sensor. The `structure` field can not be empty",
        ),
        (
            {
                CONF_ADDRESS: 1234,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_COUNT: 4,
                CONF_SWAP: CONF_SWAP_NONE,
                CONF_STRUCTURE: "1s",
            },
            "Structure request 1 bytes, but 4 registers have a size of 8 bytes",
        ),
        (
            {
                CONF_ADDRESS: 1234,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_COUNT: 1,
                CONF_STRUCTURE: "2s",
                CONF_SWAP: CONF_SWAP_WORD,
            },
            "Error in sensor test_sensor swap(word) not possible due to the registers count: 1, needed: 2",
        ),
    ],
)
async def test_config_wrong_struct_sensor(
    hass, caplog, do_config, error_message, mock_pymodbus
):
    """Run test for sensor with wrong struct."""

    config_sensor = {
        CONF_NAME: SENSOR_NAME,
        **do_config,
    }
    caplog.set_level(logging.WARNING)
    caplog.clear()

    await base_config_test(
        hass,
        config_sensor,
        SENSOR_NAME,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        None,
        method_discovery=True,
        expect_setup_to_fail=True,
    )

    assert caplog.text.count(error_message)


@pytest.mark.parametrize(
    "cfg,regs,expected",
    [
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0],
            "0",
        ),
        (
            {},
            [0x8000],
            "-32768",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 1,
                CONF_OFFSET: 13,
                CONF_PRECISION: 0,
            },
            [7],
            "20",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 3,
                CONF_OFFSET: 13,
                CONF_PRECISION: 0,
            },
            [7],
            "34",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 3,
                CONF_OFFSET: 13,
                CONF_PRECISION: 4,
            },
            [7],
            "34.0000",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 1.5,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [1],
            "2",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: "1.5",
                CONF_OFFSET: "5",
                CONF_PRECISION: "1",
            },
            [9],
            "18.5",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 2.4,
                CONF_OFFSET: 0,
                CONF_PRECISION: 2,
            },
            [1],
            "2.40",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 1,
                CONF_OFFSET: -10.3,
                CONF_PRECISION: 1,
            },
            [2],
            "-8.3",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            "-1985229329",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            str(0x89ABCDEF),
        ),
        (
            {
                CONF_COUNT: 4,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF, 0x0123, 0x4567],
            "9920249030613615975",
        ),
        (
            {
                CONF_COUNT: 4,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 2,
                CONF_OFFSET: 3,
                CONF_PRECISION: 0,
            },
            [0x0123, 0x4567, 0x89AB, 0xCDEF],
            "163971058432973793",
        ),
        (
            {
                CONF_COUNT: 4,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 2.0,
                CONF_OFFSET: 3.0,
                CONF_PRECISION: 0,
            },
            [0x0123, 0x4567, 0x89AB, 0xCDEF],
            "163971058432973792",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            str(0x89ABCDEF),
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            str(0x89ABCDEF),
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DATA_TYPE_FLOAT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 5,
            },
            [16286, 1617],
            "1.23457",
        ),
        (
            {
                CONF_COUNT: 8,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DATA_TYPE_STRING,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x3037, 0x2D30, 0x352D, 0x3230, 0x3230, 0x2031, 0x343A, 0x3335],
            "07-05-2020 14:35",
        ),
        (
            {
                CONF_COUNT: 8,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DATA_TYPE_STRING,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            None,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            None,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SWAP: CONF_SWAP_NONE,
            },
            [0x0102],
            str(int(0x0102)),
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x0201],
            str(int(0x0102)),
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x0102, 0x0304],
            str(int(0x02010403)),
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SWAP: CONF_SWAP_WORD,
            },
            [0x0102, 0x0304],
            str(int(0x03040102)),
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_DATA_TYPE: DATA_TYPE_INT,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
            },
            [0x0102, 0x0304],
            str(int(0x04030201)),
        ),
    ],
)
async def test_all_sensor(hass, cfg, regs, expected):
    """Run test for sensor."""

    state = await base_test(
        hass,
        {CONF_NAME: SENSOR_NAME, CONF_ADDRESS: 1234, **cfg},
        SENSOR_NAME,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "cfg,regs,expected",
    [
        (
            {
                CONF_COUNT: 8,
                CONF_PRECISION: 2,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_STRUCTURE: ">4f",
            },
            # floats: 7.931250095367432, 10.600000381469727,
            #         1.000879611487865e-28, 10.566553115844727
            [0x40FD, 0xCCCD, 0x4129, 0x999A, 0x10FD, 0xC0CD, 0x4129, 0x109A],
            "7.93,10.60,0.00,10.57",
        ),
        (
            {
                CONF_COUNT: 4,
                CONF_PRECISION: 0,
                CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
                CONF_STRUCTURE: ">2i",
            },
            [0x0000, 0x0100, 0x0000, 0x0032],
            "256,50",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_PRECISION: 0,
                CONF_DATA_TYPE: DATA_TYPE_INT,
            },
            [0x0101],
            "257",
        ),
    ],
)
async def test_struct_sensor(hass, cfg, regs, expected):
    """Run test for sensor struct."""

    state = await base_test(
        hass,
        {CONF_NAME: SENSOR_NAME, CONF_ADDRESS: 1234, **cfg},
        SENSOR_NAME,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "mock_test_state",
    [(State(ENTITY_ID, "117"),)],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: SENSOR_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 0,
                }
            ]
        },
    ],
)
async def test_restore_state_sensor(hass, mock_test_state, mock_modbus):
    """Run test for sensor restore state."""
    assert hass.states.get(ENTITY_ID).state == mock_test_state[0].state


async def test_service_sensor_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""
    config = {
        CONF_SENSORS: [
            {
                CONF_NAME: SENSOR_NAME,
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
            }
        ]
    }
    mock_pymodbus.read_input_registers.return_value = ReadResult([27])
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "27"
    mock_pymodbus.read_input_registers.return_value = ReadResult([32])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "32"
