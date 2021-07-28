"""The tests for the Modbus init.

This file is responsible for testing:
- pymodbus API
- Functionality of class ModbusHub
- Coverage 100%:
    __init__.py
    const.py
    modbus.py
    validators.py
    baseplatform.py (only BasePlatform)

It uses binary_sensors/sensors to do black box testing of the read calls.
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
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)
from homeassistant.components.modbus.validators import (
    number_validator,
    struct_validator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COUNT,
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_STRUCTURE,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import ReadResult

from tests.common import async_fire_time_changed

TEST_SENSOR_NAME = "testSensor"
TEST_ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_SENSOR_NAME}"
TEST_HOST = "modbusTestHost"
TEST_MODBUS_NAME = "modbusTest"


@pytest.fixture
async def mock_modbus_with_pymodbus(hass, caplog, do_config, mock_pymodbus):
    """Load integration modbus using mocked pymodbus."""
    caplog.clear()
    caplog.set_level(logging.ERROR)
    config = {DOMAIN: do_config}
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert DOMAIN in hass.config.components
    assert caplog.text == ""
    yield mock_pymodbus


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
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DATA_TYPE_STRING,
        },
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DATA_TYPE_INT,
        },
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SWAP: CONF_SWAP_BYTE,
        },
    ],
)
async def test_ok_struct_validator(do_config):
    """Test struct validator."""
    try:
        struct_validator(do_config)
    except vol.Invalid:
        pytest.fail("struct_validator unexpected exception")


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 8,
            CONF_DATA_TYPE: DATA_TYPE_INT,
        },
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 8,
            CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
        },
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 8,
            CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
            CONF_STRUCTURE: "no good",
        },
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 20,
            CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
            CONF_STRUCTURE: ">f",
        },
        {
            CONF_NAME: TEST_SENSOR_NAME,
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_CUSTOM,
            CONF_STRUCTURE: ">f",
            CONF_SWAP: CONF_SWAP_WORD,
        },
    ],
)
async def test_exception_struct_validator(do_config):
    """Test struct validator."""
    try:
        struct_validator(do_config)
    except vol.Invalid:
        return
    pytest.fail("struct_validator missing exception")


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
        {
            # Special test for scan_interval validator with scan_interval: 0
            CONF_TYPE: "tcp",
            CONF_HOST: TEST_HOST,
            CONF_PORT: 5501,
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_SENSOR_NAME,
                    CONF_ADDRESS: 117,
                    CONF_SCAN_INTERVAL: 0,
                }
            ],
        },
    ],
)
async def test_config_modbus(hass, caplog, mock_modbus_with_pymodbus):
    """Run configuration test for modbus."""


VALUE = "value"
FUNC = "func"
DATA = "data"
SERVICE = "service"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
        },
    ],
)
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
@pytest.mark.parametrize(
    "do_return",
    [
        {VALUE: ReadResult([0x0001]), DATA: ""},
        {VALUE: ExceptionResponse(0x06), DATA: "Pymodbus:"},
        {VALUE: IllegalFunctionRequest(0x06), DATA: "Pymodbus:"},
        {VALUE: ModbusException("fail write_"), DATA: "Pymodbus:"},
    ],
)
async def test_pb_service_write(
    hass, do_write, do_return, caplog, mock_modbus_with_pymodbus
):
    """Run test for service write_register."""

    func_name = {
        CALL_TYPE_WRITE_COIL: mock_modbus_with_pymodbus.write_coil,
        CALL_TYPE_WRITE_COILS: mock_modbus_with_pymodbus.write_coils,
        CALL_TYPE_WRITE_REGISTER: mock_modbus_with_pymodbus.write_register,
        CALL_TYPE_WRITE_REGISTERS: mock_modbus_with_pymodbus.write_registers,
    }

    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
        ATTR_UNIT: 17,
        ATTR_ADDRESS: 16,
        do_write[DATA]: do_write[VALUE],
    }
    mock_modbus_with_pymodbus.reset_mock()
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    func_name[do_write[FUNC]].return_value = do_return[VALUE]
    await hass.services.async_call(DOMAIN, do_write[SERVICE], data, blocking=True)
    assert func_name[do_write[FUNC]].called
    assert func_name[do_write[FUNC]].call_args[0] == (
        data[ATTR_ADDRESS],
        data[do_write[DATA]],
    )
    if do_return[DATA]:
        assert caplog.messages[-1].startswith("Pymodbus:")


@pytest.fixture
async def mock_modbus_read_pymodbus(
    hass,
    do_group,
    do_type,
    do_scan_interval,
    do_return,
    do_exception,
    caplog,
    mock_pymodbus,
):
    """Load integration modbus using mocked pymodbus."""
    caplog.clear()
    caplog.set_level(logging.ERROR)
    mock_pymodbus.read_coils.side_effect = do_exception
    mock_pymodbus.read_discrete_inputs.side_effect = do_exception
    mock_pymodbus.read_input_registers.side_effect = do_exception
    mock_pymodbus.read_holding_registers.side_effect = do_exception
    mock_pymodbus.read_coils.return_value = do_return
    mock_pymodbus.read_discrete_inputs.return_value = do_return
    mock_pymodbus.read_input_registers.return_value = do_return
    mock_pymodbus.read_holding_registers.return_value = do_return
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
                        CONF_SCAN_INTERVAL: do_scan_interval,
                    }
                ],
            }
        ],
    }
    now = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()
    assert DOMAIN in hass.config.components
    assert caplog.text == ""
    now = now + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 60)
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
    yield mock_pymodbus


@pytest.mark.parametrize(
    "do_domain, do_group,do_type,do_scan_interval",
    [
        [SENSOR_DOMAIN, CONF_SENSORS, CALL_TYPE_REGISTER_HOLDING, 10],
        [SENSOR_DOMAIN, CONF_SENSORS, CALL_TYPE_REGISTER_INPUT, 10],
        [BINARY_SENSOR_DOMAIN, CONF_BINARY_SENSORS, CALL_TYPE_DISCRETE, 10],
        [BINARY_SENSOR_DOMAIN, CONF_BINARY_SENSORS, CALL_TYPE_COIL, 1],
    ],
)
@pytest.mark.parametrize(
    "do_return,do_exception,do_expect_state,do_expect_value",
    [
        [ReadResult([1]), None, STATE_ON, "1"],
        [IllegalFunctionRequest(0x99), None, STATE_UNAVAILABLE, STATE_UNAVAILABLE],
        [ExceptionResponse(0x99), None, STATE_UNAVAILABLE, STATE_UNAVAILABLE],
        [
            ReadResult([1]),
            ModbusException("fail read_"),
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
        ],
    ],
)
async def test_pb_read(
    hass, do_domain, do_expect_state, do_expect_value, caplog, mock_modbus_read_pymodbus
):
    """Run test for different read."""

    # Check state
    entity_id = f"{do_domain}.{TEST_SENSOR_NAME}"
    state = hass.states.get(entity_id).state
    assert hass.states.get(entity_id).state

    # this if is needed to avoid explode the
    if do_domain == SENSOR_DOMAIN:
        do_expect = do_expect_value
    else:
        do_expect = do_expect_state
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
        assert await async_setup_component(hass, DOMAIN, config) is False
        await hass.async_block_till_done()
        assert caplog.messages[0].startswith("Pymodbus: Modbus Error: test")
        assert caplog.records[0].levelname == "ERROR"
        assert mock_pb.called


async def test_pymodbus_close_fail(hass, caplog, mock_pymodbus):
    """Run test for failing pymodbus close."""
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
    mock_pymodbus.connect.return_value = True
    mock_pymodbus.close.side_effect = ModbusException("close fail")
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    # Close() is called as part of teardown


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
