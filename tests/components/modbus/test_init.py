"""The tests for the Modbus init."""
from datetime import timedelta
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse, IllegalFunctionRequest
import pytest
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.modbus import number
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
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
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


@pytest.mark.parametrize(
    "value,value_type",
    [
        (15, int),
        (15.1, float),
        ("15", int),
        ("15.1", float),
        (-15, int),
        (-15.1, float),
        ("-15", int),
        ("-15.1", float),
    ],
)
async def test_number_validator(value, value_type):
    """Test number validator."""

    assert isinstance(number(value), value_type)


async def test_number_exception():
    """Test number exception."""

    try:
        number("x15.1")
    except (vol.Invalid):
        return

    pytest.fail("Number not throwing exception")


async def _config_helper(hass, do_config, caplog):
    """Run test for modbus."""

    config = {DOMAIN: do_config}

    caplog.set_level(logging.ERROR)
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert DOMAIN in hass.config.components
    assert len(caplog.records) == 0


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: "modbusTestHost",
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
    ],
)
async def test_config_modbus(hass, caplog, do_config, mock_pymodbus):
    """Run test for modbus."""
    await _config_helper(hass, do_config, caplog)


async def test_config_multiple_modbus(hass, caplog, mock_pymodbus):
    """Run test for multiple modbus."""
    do_config = [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: TEST_MODBUS_NAME,
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
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
    ]

    await _config_helper(hass, do_config, caplog)


async def test_pb_service_write_register(hass, caplog, mock_modbus):
    """Run test for service write_register."""

    # Pymodbus write single, response OK.
    data = {ATTR_HUB: TEST_MODBUS_NAME, ATTR_UNIT: 17, ATTR_ADDRESS: 16, ATTR_VALUE: 15}
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert mock_modbus.write_register.called
    assert mock_modbus.write_register.call_args[0] == (
        data[ATTR_ADDRESS],
        data[ATTR_VALUE],
    )

    # Pymodbus write single, response error or exception
    caplog.set_level(logging.DEBUG)
    mock_modbus.write_register.return_value = ExceptionResponse(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_register.return_value = IllegalFunctionRequest(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_register.side_effect = ModbusException("fail write_")
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")

    # Pymodbus write multiple, response OK.
    data[ATTR_VALUE] = [1, 2, 3]
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert mock_modbus.write_registers.called
    assert mock_modbus.write_registers.call_args[0] == (
        data[ATTR_ADDRESS],
        data[ATTR_VALUE],
    )

    # Pymodbus write multiple, response error or exception
    mock_modbus.write_registers.return_value = ExceptionResponse(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_registers.return_value = IllegalFunctionRequest(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_registers.side_effect = ModbusException("fail write_")
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True)


async def test_pb_service_write_coil(hass, caplog, mock_modbus):
    """Run test for service write_coil."""

    # Pymodbus write single, response OK.
    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
        ATTR_UNIT: 17,
        ATTR_ADDRESS: 16,
        ATTR_STATE: False,
    }
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert mock_modbus.write_coil.called
    assert mock_modbus.write_coil.call_args[0] == (
        data[ATTR_ADDRESS],
        data[ATTR_STATE],
    )

    # Pymodbus write single, response error or exception
    caplog.set_level(logging.DEBUG)
    mock_modbus.write_coil.return_value = ExceptionResponse(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_coil.return_value = IllegalFunctionRequest(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_coil.side_effect = ModbusException("fail write_")
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)

    # Pymodbus write multiple, response OK.
    data[ATTR_STATE] = [True, False, True]
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert mock_modbus.write_coils.called
    assert mock_modbus.write_coils.call_args[0] == (
        data[ATTR_ADDRESS],
        data[ATTR_STATE],
    )

    # Pymodbus write multiple, response error or exception
    mock_modbus.write_coils.return_value = ExceptionResponse(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_coils.return_value = IllegalFunctionRequest(0x06)
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")
    mock_modbus.write_coils.side_effect = ModbusException("fail write_")
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
    assert caplog.messages[-1].startswith("Pymodbus:")


async def _read_helper(hass, do_group, do_type, do_return, do_exception, mock_pymodbus):
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
                CONF_NAME: TEST_MODBUS_NAME,
                do_group: {
                    CONF_INPUT_TYPE: do_type,
                    CONF_NAME: TEST_SENSOR_NAME,
                    CONF_ADDRESS: 51,
                },
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
                CONF_HOST: "modbusTestHost",
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
                CONF_HOST: "modbusTestHost",
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
