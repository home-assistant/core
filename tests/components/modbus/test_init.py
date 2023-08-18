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

from freezegun.api import FrozenDateTimeFactory
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse, IllegalFunctionRequest
import pytest
import voluptuous as vol

from homeassistant import config as hass_config
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_SLAVE,
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
    CONF_MSG_WAIT,
    CONF_PARITY,
    CONF_SLAVE_COUNT,
    CONF_STOPBITS,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_DOMAIN as DOMAIN,
    RTUOVERTCP,
    SERIAL,
    SERVICE_RESTART,
    SERVICE_STOP,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
    TCP,
    UDP,
    DataType,
)
from homeassistant.components.modbus.validators import (
    duplicate_entity_validator,
    duplicate_modbus_validator,
    nan_validator,
    number_validator,
    struct_validator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_STATE,
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
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import (
    TEST_ENTITY_NAME,
    TEST_MODBUS_HOST,
    TEST_MODBUS_NAME,
    TEST_PORT_SERIAL,
    TEST_PORT_TCP,
    ReadResult,
)

from tests.common import async_fire_time_changed, get_fixture_path


@pytest.fixture(name="mock_modbus_with_pymodbus")
async def mock_modbus_with_pymodbus_fixture(hass, caplog, do_config, mock_pymodbus):
    """Load integration modbus using mocked pymodbus."""
    caplog.clear()
    caplog.set_level(logging.ERROR)
    config = {DOMAIN: do_config}
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert DOMAIN in hass.config.components
    assert caplog.text == ""
    return mock_pymodbus


async def test_number_validator() -> None:
    """Test number validator."""

    for value, value_type in (
        (15, int),
        (15.1, float),
        ("15", int),
        ("15.1", float),
        (-15, int),
        (-15.1, float),
        ("-15", int),
        ("-15.1", float),
    ):
        assert isinstance(number_validator(value), value_type)

    try:
        number_validator("x15.1")
    except vol.Invalid:
        return
    pytest.fail("Number_validator not throwing exception")


async def test_nan_validator() -> None:
    """Test number validator."""

    for value, value_type in (
        (15, int),
        ("15", int),
        ("abcdef", int),
        ("0xabcdef", int),
    ):
        assert isinstance(nan_validator(value), value_type)

    with pytest.raises(vol.Invalid):
        nan_validator("x15")
    with pytest.raises(vol.Invalid):
        nan_validator("not a hex string")


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DataType.STRING,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_DATA_TYPE: DataType.INT32,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_DATA_TYPE: DataType.INT32,
            CONF_SWAP: CONF_SWAP_BYTE,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DataType.CUSTOM,
            CONF_STRUCTURE: ">i",
        },
    ],
)
async def test_ok_struct_validator(do_config) -> None:
    """Test struct validator."""
    try:
        struct_validator(do_config)
    except vol.Invalid:
        pytest.fail("struct_validator unexpected exception")


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 8,
            CONF_DATA_TYPE: "int",
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 8,
            CONF_DATA_TYPE: DataType.CUSTOM,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 8,
            CONF_DATA_TYPE: DataType.CUSTOM,
            CONF_STRUCTURE: "no good",
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 20,
            CONF_DATA_TYPE: DataType.CUSTOM,
            CONF_STRUCTURE: ">f",
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DataType.CUSTOM,
            CONF_STRUCTURE: ">f",
            CONF_SWAP: CONF_SWAP_WORD,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DataType.STRING,
            CONF_STRUCTURE: ">f",
            CONF_SWAP: CONF_SWAP_WORD,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DataType.CUSTOM,
            CONF_STRUCTURE: ">f",
            CONF_SLAVE_COUNT: 5,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_DATA_TYPE: DataType.STRING,
            CONF_SLAVE_COUNT: 2,
        },
        {
            CONF_NAME: TEST_ENTITY_NAME,
            CONF_DATA_TYPE: DataType.INT16,
            CONF_SWAP: CONF_SWAP_WORD,
        },
    ],
)
async def test_exception_struct_validator(do_config) -> None:
    """Test struct validator."""
    try:
        struct_validator(do_config)
    except vol.Invalid:
        return
    pytest.fail("struct_validator missing exception")


@pytest.mark.parametrize(
    "do_config",
    [
        [
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            },
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST + " 2",
                CONF_PORT: TEST_PORT_TCP,
            },
        ],
        [
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            },
            {
                CONF_NAME: TEST_MODBUS_NAME + " 2",
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            },
        ],
    ],
)
async def test_duplicate_modbus_validator(do_config) -> None:
    """Test duplicate modbus validator."""
    duplicate_modbus_validator(do_config)
    assert len(do_config) == 1


@pytest.mark.parametrize(
    "do_config",
    [
        [
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 0,
                    },
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 119,
                        CONF_SLAVE: 0,
                    },
                ],
            }
        ],
        [
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 0,
                    },
                    {
                        CONF_NAME: TEST_ENTITY_NAME + " 2",
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 0,
                    },
                ],
            }
        ],
    ],
)
async def test_duplicate_entity_validator(do_config) -> None:
    """Test duplicate entity validator."""
    duplicate_entity_validator(do_config)
    assert len(do_config[0][CONF_SENSORS]) == 1


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: TCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
        },
        {
            CONF_TYPE: TCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: UDP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
        },
        {
            CONF_TYPE: UDP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: RTUOVERTCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
        },
        {
            CONF_TYPE: RTUOVERTCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: SERIAL,
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: TEST_PORT_SERIAL,
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_MSG_WAIT: 100,
        },
        {
            CONF_TYPE: SERIAL,
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "ascii",
            CONF_PORT: TEST_PORT_SERIAL,
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_NAME: TEST_MODBUS_NAME,
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: TCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
            CONF_DELAY: 5,
        },
        [
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: TEST_MODBUS_NAME,
            },
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: f"{TEST_MODBUS_NAME} 2",
            },
            {
                CONF_TYPE: SERIAL,
                CONF_BAUDRATE: 9600,
                CONF_BYTESIZE: 8,
                CONF_METHOD: "rtu",
                CONF_PORT: TEST_PORT_SERIAL,
                CONF_PARITY: "E",
                CONF_STOPBITS: 1,
                CONF_NAME: f"{TEST_MODBUS_NAME} 3",
            },
        ],
        {
            # Special test for scan_interval validator with scan_interval: 0
            CONF_TYPE: TCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 0,
                    CONF_SCAN_INTERVAL: 0,
                }
            ],
        },
    ],
)
async def test_config_modbus(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_modbus_with_pymodbus
) -> None:
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
            CONF_TYPE: SERIAL,
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: TEST_PORT_SERIAL,
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
@pytest.mark.parametrize(
    "do_unit",
    [
        ATTR_UNIT,
        ATTR_SLAVE,
    ],
)
async def test_pb_service_write(
    hass: HomeAssistant,
    do_write,
    do_return,
    do_unit,
    caplog: pytest.LogCaptureFixture,
    mock_modbus_with_pymodbus,
) -> None:
    """Run test for service write_register."""

    func_name = {
        CALL_TYPE_WRITE_COIL: mock_modbus_with_pymodbus.write_coil,
        CALL_TYPE_WRITE_COILS: mock_modbus_with_pymodbus.write_coils,
        CALL_TYPE_WRITE_REGISTER: mock_modbus_with_pymodbus.write_register,
        CALL_TYPE_WRITE_REGISTERS: mock_modbus_with_pymodbus.write_registers,
    }

    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
        do_unit: 17,
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
        assert any(message.startswith("Pymodbus:") for message in caplog.messages)


@pytest.fixture(name="mock_modbus_read_pymodbus")
async def mock_modbus_read_pymodbus_fixture(
    hass,
    do_group,
    do_type,
    do_scan_interval,
    do_return,
    do_exception,
    caplog,
    mock_pymodbus,
    freezer: FrozenDateTimeFactory,
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
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: TEST_MODBUS_NAME,
                do_group: [
                    {
                        CONF_INPUT_TYPE: do_type,
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SLAVE: 0,
                        CONF_SCAN_INTERVAL: do_scan_interval,
                    }
                ],
            }
        ],
    }
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert DOMAIN in hass.config.components
    assert caplog.text == ""
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    return mock_pymodbus


@pytest.mark.parametrize(
    ("do_domain", "do_group", "do_type", "do_scan_interval"),
    [
        [SENSOR_DOMAIN, CONF_SENSORS, CALL_TYPE_REGISTER_HOLDING, 10],
        [SENSOR_DOMAIN, CONF_SENSORS, CALL_TYPE_REGISTER_INPUT, 10],
        [BINARY_SENSOR_DOMAIN, CONF_BINARY_SENSORS, CALL_TYPE_DISCRETE, 10],
        [BINARY_SENSOR_DOMAIN, CONF_BINARY_SENSORS, CALL_TYPE_COIL, 1],
    ],
)
@pytest.mark.parametrize(
    ("do_return", "do_exception", "do_expect_state", "do_expect_value"),
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
    hass: HomeAssistant,
    do_domain,
    do_expect_state,
    do_expect_value,
    caplog: pytest.LogCaptureFixture,
    mock_modbus_read_pymodbus,
) -> None:
    """Run test for different read."""

    # Check state
    entity_id = f"{do_domain}.{TEST_ENTITY_NAME}".replace(" ", "_")
    state = hass.states.get(entity_id).state
    assert hass.states.get(entity_id).state

    # this if is needed to avoid explode the
    if do_domain == SENSOR_DOMAIN:
        do_expect = do_expect_value
    else:
        do_expect = do_expect_state
    assert state == do_expect


async def test_pymodbus_constructor_fail(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Run test for failing pymodbus constructor."""
    config = {
        DOMAIN: [
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            }
        ]
    }
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", autospec=True
    ) as mock_pb:
        caplog.set_level(logging.ERROR)
        mock_pb.side_effect = ModbusException("test no class")
        assert await async_setup_component(hass, DOMAIN, config) is False
        await hass.async_block_till_done()
        message = f"Pymodbus: {TEST_MODBUS_NAME}: Modbus Error: test"
        assert caplog.messages[0].startswith(message)
        assert caplog.records[0].levelname == "ERROR"
        assert mock_pb.called


async def test_pymodbus_close_fail(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_pymodbus
) -> None:
    """Run test for failing pymodbus close."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            }
        ]
    }
    caplog.set_level(logging.ERROR)
    mock_pymodbus.connect.return_value = True
    mock_pymodbus.close.side_effect = ModbusException("close fail")
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    # Close() is called as part of teardown


async def test_pymodbus_connect_fail(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_pymodbus
) -> None:
    """Run test for failing pymodbus constructor."""
    config = {
        DOMAIN: [
            {
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            }
        ]
    }
    caplog.set_level(logging.WARNING)
    ExceptionMessage = "test connect exception"
    mock_pymodbus.connect.side_effect = ModbusException(ExceptionMessage)
    assert await async_setup_component(hass, DOMAIN, config) is True


async def test_delay(
    hass: HomeAssistant, mock_pymodbus, freezer: FrozenDateTimeFactory
) -> None:
    """Run test for startup delay."""

    # the purpose of this test is to test startup delay
    # We "hijiack" a binary_sensor to make a proper blackbox test.
    set_delay = 15
    set_scan_interval = 5
    entity_id = f"{BINARY_SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
    config = {
        DOMAIN: [
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_DELAY: set_delay,
                CONF_BINARY_SENSORS: [
                    {
                        CONF_INPUT_TYPE: CALL_TYPE_COIL,
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 52,
                        CONF_SLAVE: 0,
                        CONF_SCAN_INTERVAL: set_scan_interval,
                    },
                ],
            }
        ]
    }
    mock_pymodbus.read_coils.return_value = ReadResult([0x01])
    start_time = dt_util.utcnow()
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    time_sensor_active = start_time + timedelta(seconds=2)
    time_after_delay = start_time + timedelta(seconds=(set_delay))
    time_after_scan = start_time + timedelta(seconds=(set_delay + set_scan_interval))
    time_stop = time_after_scan + timedelta(seconds=10)
    now = start_time
    while now < time_stop:
        # This test assumed listeners are always fired at 0
        # microseconds which is impossible in production so
        # we use 999999 microseconds to simulate the real world.
        freezer.tick(timedelta(seconds=1, microseconds=999999))
        now = dt_util.utcnow()
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        if now > time_sensor_active:
            if now <= time_after_delay:
                assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
            elif now > time_after_scan:
                assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: TCP,
            CONF_HOST: TEST_MODBUS_HOST,
            CONF_PORT: TEST_PORT_TCP,
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 0,
                    CONF_SCAN_INTERVAL: 0,
                }
            ],
        },
    ],
)
async def test_shutdown(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_pymodbus,
    mock_modbus_with_pymodbus,
) -> None:
    """Run test for shutdown."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mock_pymodbus.close.called
    assert caplog.text == ""


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 0,
                }
            ]
        },
    ],
)
async def test_stop_restart(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_modbus
) -> None:
    """Run test for service stop."""

    caplog.set_level(logging.INFO)
    entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    hass.states.async_set(entity_id, 17)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "17"

    mock_modbus.reset_mock()
    caplog.clear()
    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
    }
    await hass.services.async_call(DOMAIN, SERVICE_STOP, data, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert mock_modbus.close.called
    assert f"modbus {TEST_MODBUS_NAME} communication closed" in caplog.text

    mock_modbus.reset_mock()
    caplog.clear()
    await hass.services.async_call(DOMAIN, SERVICE_RESTART, data, blocking=True)
    await hass.async_block_till_done()
    assert not mock_modbus.close.called
    assert mock_modbus.connect.called
    assert f"modbus {TEST_MODBUS_NAME} communication open" in caplog.text

    mock_modbus.reset_mock()
    caplog.clear()
    await hass.services.async_call(DOMAIN, SERVICE_RESTART, data, blocking=True)
    await hass.async_block_till_done()
    assert mock_modbus.close.called
    assert mock_modbus.connect.called
    assert f"modbus {TEST_MODBUS_NAME} communication closed" in caplog.text
    assert f"modbus {TEST_MODBUS_NAME} communication open" in caplog.text


@pytest.mark.parametrize("do_config", [{}])
async def test_write_no_client(hass: HomeAssistant, mock_modbus) -> None:
    """Run test for service stop and write without client."""

    mock_modbus.reset()
    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
    }
    await hass.services.async_call(DOMAIN, SERVICE_STOP, data, blocking=True)
    await hass.async_block_till_done()
    assert mock_modbus.close.called

    data = {
        ATTR_HUB: TEST_MODBUS_NAME,
        ATTR_UNIT: 17,
        ATTR_ADDRESS: 16,
        ATTR_STATE: True,
    }
    await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)


@pytest.mark.parametrize("do_config", [{}])
async def test_integration_reload(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_modbus,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Run test for integration reload."""

    caplog.set_level(logging.INFO)
    caplog.clear()

    yaml_path = get_fixture_path("configuration.yaml", "modbus")
    with mock.patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()
        for _ in range(4):
            freezer.tick(timedelta(seconds=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
    assert "Modbus reloading" in caplog.text


@pytest.mark.parametrize("do_config", [{}])
async def test_integration_reload_failed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_modbus
) -> None:
    """Run test for integration connect failure on reload."""
    caplog.set_level(logging.INFO)
    caplog.clear()

    yaml_path = get_fixture_path("configuration.yaml", "modbus")
    with mock.patch.object(
        hass_config, "YAML_CONFIG_FILE", yaml_path
    ), mock.patch.object(mock_modbus, "connect", side_effect=ModbusException("error")):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    assert "Modbus reloading" in caplog.text
    assert "connect failed, retry in pymodbus" in caplog.text


@pytest.mark.parametrize("do_config", [{}])
async def test_integration_setup_failed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_modbus
) -> None:
    """Run test for integration setup on reload."""
    with mock.patch.object(
        hass_config,
        "YAML_CONFIG_FILE",
        get_fixture_path("configuration.yaml", "modbus"),
    ):
        hass.data[DOMAIN][TEST_MODBUS_NAME].async_setup = mock.AsyncMock(
            return_value=False
        )
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()
