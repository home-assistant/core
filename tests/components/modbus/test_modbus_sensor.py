"""The tests for the Modbus sensor component."""
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COUNT,
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_PRECISION,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_REVERSE_ORDER,
    CONF_SCALE,
    CONF_SENSORS,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
    MODBUS_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PORT,
    CONF_SLAVE,
)

from .conftest import base_config_test, base_test, server_test


@pytest.mark.parametrize("do_discovery", [False, True])
@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize(
    "do_type", [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]
)
@pytest.mark.parametrize("do_server", [False, True])
@mock.patch("homeassistant.components.modbus.modbus.StartTcpServer")
async def test_config_sensor(
    mock_server,
    hass,
    do_discovery,
    do_options,
    do_type,
    do_server,
    config_modbus_server,
):
    """Run test for sensor."""
    sensor_name = "test_sensor"
    config_sensor = {
        CONF_NAME: sensor_name,
        CONF_ADDRESS: 51,
    }
    if do_options:
        config_sensor.update(
            {
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_DATA_TYPE: "int",
                CONF_PRECISION: 0,
                CONF_SCALE: 1,
                CONF_REVERSE_ORDER: False,
                CONF_OFFSET: 0,
                CONF_INPUT_TYPE: do_type,
                CONF_DEVICE_CLASS: "battery",
            }
        )
    if not do_discovery:
        # bridge difference in configuration
        config_sensor[CONF_REGISTER] = config_sensor[CONF_ADDRESS]
        del config_sensor[CONF_ADDRESS]
        if do_options:
            config_sensor[CONF_REGISTER_TYPE] = config_sensor[CONF_INPUT_TYPE]
            del config_sensor[CONF_INPUT_TYPE]
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_SENSORS,
        CONF_REGISTERS,
        method_discovery=do_discovery,
        config_modbus=config_modbus_server if do_server else None,
    )

    if do_server:
        mock_server.assert_called_once_with(
            mock.ANY,
            address=(
                config_modbus_server[MODBUS_DOMAIN][CONF_HOST],
                config_modbus_server[MODBUS_DOMAIN][CONF_PORT],
            ),
            allow_reuse_address=True,
            defer_start=True,
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
    ],
)
@pytest.mark.parametrize("do_server", [True, False])
async def test_all_sensor(do_server, config_modbus_server, hass, cfg, regs, expected):
    """Run test for sensor."""
    sensor_name = "modbus_test_sensor"

    if do_server:
        state, _ = await server_test(
            hass,
            {CONF_NAME: sensor_name, CONF_ADDRESS: 1234, CONF_SLAVE: 10, **cfg},
            sensor_name,
            SENSOR_DOMAIN,
            CONF_SENSORS,
            CONF_REGISTERS,
            regs,
            expected,
            method_discovery=True,
            scan_interval=5,
            config_modbus=config_modbus_server,
        )
    else:
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
