"""The tests for the Modbus init.

This file is responsible for testing:
- pymodbus API
- Functionality of class ModbusHub
- Coverage 100%:
    __init__.py
    base_platform.py
    const.py
    modbus.py
"""
from datetime import timedelta
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse, IllegalFunctionRequest
import pytest
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_STATE,
    ATTR_UNIT,
    ATTR_VALUE,
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_INPUT_TYPE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)
from homeassistant.components.modbus.validators import number_validator
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import TEST_MODBUS_NAME, ReadResult

from tests.common import async_fire_time_changed

TEST_SENSOR_NAME = "testSensor"
TEST_ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_SENSOR_NAME}"
TEST_HOST = "modbusTestHost"


async def test_number_validator():
    """Test number validator."""

    for value, value_type in [
        (15, int),
        (15.1, float),
        ("15", int),
        ("15.1", float),
        (-15, int),
        (-15.1, float),
        ("-15", int),
        ("-15.1", float),
    ]:
        assert isinstance(number_validator(value), value_type)

    try:
        number_validator("x15.1")
    except (vol.Invalid):
        return
    pytest.fail("Number_validator not throwing exception")


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
        },
        {
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
            CONF_DELAY: 5,
        },
        [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: TEST_HOST,
                CONF_PORT: 5501,
                CONF_NAME: TEST_MODBUS_NAME,
            },
            {
                CONF_TYPE: "tcp",
                CONF_HOST: TEST_HOST,
                CONF_PORT: 5501,
                CONF_NAME: TEST_MODBUS_NAME + "2",
            },
            {
                CONF_TYPE: "serial",
                CONF_BAUDRATE: 9600,
                CONF_BYTESIZE: 8,
                CONF_METHOD: "rtu",
                CONF_PORT: "usb01",
                CONF_PARITY: "E",
                CONF_STOPBITS: 1,
                CONF_NAME: TEST_MODBUS_NAME + "3",
            },
        ],
    ],
)
async def test_config_modbus(hass, caplog, do_config, mock_pymodbus):
    """Run configuration test for modbus."""
    config = {DOMAIN: do_config}
    caplog.set_level(logging.ERROR)
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert DOMAIN in hass.config.components
    assert len(caplog.records) == 0


VALUE = "value"
FUNC = "func"
DATA = "data"
SERVICE = "service"


@pytest.mark.parametrize(
    "do_write",
    [
        {
            DATA: ATTR_VALUE,
            VALUE: 15,
            SERVICE: SERVICE_WRITE_REGISTER,
            FUNC: CALL_TYPE_WRITE_REGISTER,
        },
        {
            DATA: ATTR_VALUE,
            VALUE: [1, 2, 3],
            SERVICE: SERVICE_WRITE_REGISTER,
            FUNC: CALL_TYPE_WRITE_REGISTERS,
        },
        {
            DATA: ATTR_STATE,
            VALUE: False,
            SERVICE: SERVICE_WRITE_COIL,
            FUNC: CALL_TYPE_WRITE_COIL,
        },
        {
            DATA: ATTR_STATE,
            VALUE: [True, False, True],
            SERVICE: SERVICE_WRITE_COIL,
            FUNC: CALL_TYPE_WRITE_COILS,
        },
    ],
)
async def test_pb_service_write(hass, do_write, caplog, mock_modbus):
    """Run test for service write_register."""

    func_name = {
        CALL_TYPE_WRITE_COIL: mock_modbus.write_coil,
        CALL_TYPE_WRITE_COILS: mock_modbus.write_coils,
        CALL_TYPE_WRITE_REGISTER: mock_modbus.write_register,
        CALL_TYPE_WRITE_REGISTERS: mock_modbus.write_registers,
    }

    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
        ATTR_UNIT: 17,
        ATTR_ADDRESS: 16,
        do_write[DATA]: do_write[VALUE],
    }
    await hass.services.async_call(DOMAIN, do_write[SERVICE], data, blocking=True)
    assert func_name[do_write[FUNC]].called
    assert func_name[do_write[FUNC]].call_args[0] == (
        data[ATTR_ADDRESS],
        data[do_write[DATA]],
    )
    mock_modbus.reset_mock()

    for return_value in [
        ExceptionResponse(0x06),
        IllegalFunctionRequest(0x06),
        ModbusException("fail write_"),
    ]:
        caplog.set_level(logging.DEBUG)
        func_name[do_write[FUNC]].return_value = return_value
        await hass.services.async_call(DOMAIN, do_write[SERVICE], data, blocking=True)
        assert func_name[do_write[FUNC]].called
        assert caplog.messages[-1].startswith("Pymodbus:")
        mock_modbus.reset_mock()


async def _read_helper(hass, do_group, do_type, do_return, do_exception, mock_pymodbus):
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: TEST_HOST,
                CONF_PORT: 5501,
                CONF_NAME: TEST_MODBUS_NAME,
                do_group: [
                    {
                        CONF_INPUT_TYPE: do_type,
                        CONF_NAME: TEST_SENSOR_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SCAN_INTERVAL: 1,
                    }
                ],
            }
        ]
    }
    mock_pymodbus.read_coils.side_effect = do_exception
    mock_pymodbus.read_discrete_inputs.side_effect = do_exception
    mock_pymodbus.read_input_registers.side_effect = do_exception
    mock_pymodbus.read_holding_registers.side_effect = do_exception
    mock_pymodbus.read_coils.return_value = do_return
    mock_pymodbus.read_discrete_inputs.return_value = do_return
    mock_pymodbus.read_input_registers.return_value = do_return
    mock_pymodbus.read_holding_registers.return_value = do_return
    now = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()
    now = now + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 60)
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "do_return,do_exception,do_expect",
    [
        [ReadResult([7]), None, "7"],
        [IllegalFunctionRequest(0x99), None, STATE_UNAVAILABLE],
        [ExceptionResponse(0x99), None, STATE_UNAVAILABLE],
        [ReadResult([7]), ModbusException("fail read_"), STATE_UNAVAILABLE],
    ],
)
@pytest.mark.parametrize(
    "do_type",
    [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT],
)
async def test_pb_read_value(
    hass, caplog, do_type, do_return, do_exception, do_expect, mock_pymodbus
):
    """Run test for different read."""

    # the purpose of this test is to test the special
    # return values from pymodbus:
    #     ExceptionResponse, IllegalResponse
    # and exceptions.
    # We "hijiack" binary_sensor and sensor in order
    # to make a proper blackbox test.
    await _read_helper(
        hass, CONF_SENSORS, do_type, do_return, do_exception, mock_pymodbus
    )

    # Check state
    entity_id = f"{SENSOR_DOMAIN}.{TEST_SENSOR_NAME}"
    assert hass.states.get(entity_id).state


@pytest.mark.parametrize(
    "do_return,do_exception,do_expect",
    [
        [ReadResult([0x01]), None, STATE_ON],
        [IllegalFunctionRequest(0x99), None, STATE_UNAVAILABLE],
        [ExceptionResponse(0x99), None, STATE_UNAVAILABLE],
        [ReadResult([7]), ModbusException("fail read_"), STATE_UNAVAILABLE],
    ],
)
@pytest.mark.parametrize("do_type", [CALL_TYPE_DISCRETE, CALL_TYPE_COIL])
async def test_pb_read_state(
    hass, caplog, do_type, do_return, do_exception, do_expect, mock_pymodbus
):
    """Run test for different read."""

    # the purpose of this test is to test the special
    # return values from pymodbus:
    #     ExceptionResponse, IllegalResponse
    # and exceptions.
    # We "hijiack" binary_sensor and sensor in order
    # to make a proper blackbox test.
    await _read_helper(
        hass, CONF_BINARY_SENSORS, do_type, do_return, do_exception, mock_pymodbus
    )

    # Check state
    entity_id = f"{BINARY_SENSOR_DOMAIN}.{TEST_SENSOR_NAME}"
    state = hass.states.get(entity_id).state
    assert state == do_expect


async def test_pymodbus_constructor_fail(hass, caplog):
    """Run test for failing pymodbus constructor."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: TEST_HOST,
                CONF_PORT: 5501,
            }
        ]
    }
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient"
    ) as mock_pb:
        caplog.set_level(logging.ERROR)
        mock_pb.side_effect = ModbusException("test no class")
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert mock_pb.called


async def test_pymodbus_connect_fail(hass, caplog, mock_pymodbus):
    """Run test for failing pymodbus constructor."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: TEST_HOST,
                CONF_PORT: 5501,
            }
        ]
    }
    caplog.set_level(logging.ERROR)
    mock_pymodbus.connect.side_effect = ModbusException("test connect fail")
    mock_pymodbus.close.side_effect = ModbusException("test connect fail")
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"


async def test_delay(hass, mock_pymodbus):
    """Run test for startup delay."""

    # the purpose of this test is to test startup delay
    # We "hijiack" a binary_sensor to make a proper blackbox test.
    test_delay = 15
    test_scan_interval = 5
    entity_id = f"{BINARY_SENSOR_DOMAIN}.{TEST_SENSOR_NAME}"
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: TEST_HOST,
                CONF_PORT: 5501,
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_DELAY: test_delay,
                CONF_BINARY_SENSORS: [
                    {
                        CONF_INPUT_TYPE: CALL_TYPE_COIL,
                        CONF_NAME: f"{TEST_SENSOR_NAME}",
                        CONF_ADDRESS: 52,
                        CONF_SCAN_INTERVAL: test_scan_interval,
                    },
                ],
            }
        ]
    }
    mock_pymodbus.read_coils.return_value = ReadResult([0x01])
    now = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()

    # pass first scan_interval
    start_time = now
    now = now + timedelta(seconds=(test_scan_interval + 1))
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    stop_time = start_time + timedelta(seconds=(test_delay + 1))
    step_timedelta = timedelta(seconds=1)
    while now < stop_time:
        now = now + step_timedelta
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()
            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    now = now + step_timedelta + timedelta(seconds=2)
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_ON
