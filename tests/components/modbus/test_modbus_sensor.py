"""The tests for the Modbus sensor component."""
import logging
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_PRECISION,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_REVERSE_ORDER,
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
    CONF_SENSORS,
    CONF_SLAVE,
    CONF_STRUCTURE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State

from .conftest import ReadResult, base_config_test, base_test, prepare_service_update


@pytest.mark.parametrize(
    "do_discovery, do_config",
    [
        (
            False,
            {
                CONF_REGISTER: 51,
            },
        ),
        (
            False,
            {
                CONF_REGISTER: 51,
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_DATA_TYPE: "int",
                CONF_PRECISION: 0,
                CONF_SCALE: 1,
                CONF_REVERSE_ORDER: False,
                CONF_OFFSET: 0,
                CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
        (
            False,
            {
                CONF_REGISTER: 51,
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_DATA_TYPE: "int",
                CONF_PRECISION: 0,
                CONF_SCALE: 1,
                CONF_REVERSE_ORDER: False,
                CONF_OFFSET: 0,
                CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_DATA_TYPE: "int",
                CONF_PRECISION: 0,
                CONF_SCALE: 1,
                CONF_REVERSE_ORDER: False,
                CONF_OFFSET: 0,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_DATA_TYPE: "int",
                CONF_PRECISION: 0,
                CONF_SCALE: 1,
                CONF_REVERSE_ORDER: False,
                CONF_OFFSET: 0,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_COUNT: 1,
                CONF_SWAP: CONF_SWAP_NONE,
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_COUNT: 1,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_COUNT: 2,
                CONF_SWAP: CONF_SWAP_WORD,
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_COUNT: 2,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
            },
        ),
    ],
)
async def test_config_sensor(hass, do_discovery, do_config):
    """Run test for sensor."""
    sensor_name = "test_sensor"
    config_sensor = {
        CONF_NAME: sensor_name,
        **do_config,
    }
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        CONF_REGISTERS,
        method_discovery=do_discovery,
    )


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_ADDRESS: 1234,
            CONF_COUNT: 8,
            CONF_PRECISION: 2,
            CONF_DATA_TYPE: DATA_TYPE_INT,
        },
        {
            CONF_ADDRESS: 1234,
            CONF_COUNT: 8,
            CONF_PRECISION: 2,
            CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
            CONF_STRUCTURE: ">no struct",
        },
        {
            CONF_ADDRESS: 1234,
            CONF_COUNT: 2,
            CONF_PRECISION: 2,
            CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
            CONF_STRUCTURE: ">4f",
        },
    ],
)
async def test_config_wrong_struct_sensor(hass, do_config):
    """Run test for sensor with wrong struct."""

    sensor_name = "test_sensor"
    config_sensor = {
        CONF_NAME: sensor_name,
        **do_config,
    }
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        None,
        method_discovery=True,
    )


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
                CONF_COUNT: 2,
                CONF_DATA_TYPE: DATA_TYPE_UINT,
                CONF_REVERSE_ORDER: True,
            },
            [0x89AB, 0xCDEF],
            str(0xCDEF89AB),
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

    sensor_name = "modbus_test_sensor"
    state = await base_test(
        hass,
        {CONF_NAME: sensor_name, CONF_ADDRESS: 1234, **cfg},
        sensor_name,
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

    sensor_name = "modbus_test_sensor"
    state = await base_test(
        hass,
        {CONF_NAME: sensor_name, CONF_ADDRESS: 1234, **cfg},
        sensor_name,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


async def test_restore_state_sensor(hass):
    """Run test for sensor restore state."""

    sensor_name = "test_sensor"
    test_value = "117"
    config_sensor = {CONF_NAME: sensor_name, CONF_ADDRESS: 17}
    with mock.patch(
        "homeassistant.components.modbus.sensor.ModbusRegisterSensor.async_get_last_state"
    ) as mock_get_last_state:
        mock_get_last_state.return_value = State(
            f"{SENSOR_DOMAIN}.{sensor_name}", f"{test_value}"
        )

        await base_config_test(
            hass,
            config_sensor,
            sensor_name,
            SENSOR_DOMAIN,
            CONF_SENSORS,
            None,
            method_discovery=True,
        )
        entity_id = f"{SENSOR_DOMAIN}.{sensor_name}"
        assert hass.states.get(entity_id).state == test_value


@pytest.mark.parametrize(
    "swap_type",
    [CONF_SWAP_WORD, CONF_SWAP_WORD_BYTE],
)
async def test_swap_sensor_wrong_config(hass, caplog, swap_type):
    """Run test for sensor swap."""
    sensor_name = "modbus_test_sensor"
    config = {
        CONF_NAME: sensor_name,
        CONF_ADDRESS: 1234,
        CONF_COUNT: 1,
        CONF_SWAP: swap_type,
        CONF_DATA_TYPE: DATA_TYPE_INT,
    }

    caplog.set_level(logging.ERROR)
    caplog.clear()
    await base_config_test(
        hass,
        config,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        None,
        method_discovery=True,
        expect_init_to_fail=True,
    )
    assert caplog.messages[-1].startswith("Error in sensor " + sensor_name + " swap")


async def test_service_sensor_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    entity_id = "sensor.test"
    config = {
        CONF_SENSORS: [
            {
                CONF_NAME: "test",
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
            }
        ]
    }
    mock_pymodbus.read_input_registers.return_value = ReadResult([27])
    await prepare_service_update(
        hass,
        config,
        entity_id,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == "27"
    mock_pymodbus.read_input_registers.return_value = ReadResult([32])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == "32"
