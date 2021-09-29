"""The tests for the Modbus sensor component."""
import copy
from dataclasses import dataclass
from datetime import timedelta
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import MODBUS_DOMAIN as DOMAIN, TCP
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, mock_restore_cache

TEST_MODBUS_NAME = "modbusTest"
TEST_ENTITY_NAME = "test_entity"
TEST_MODBUS_HOST = "modbusHost"
TEST_PORT_TCP = 5501
TEST_PORT_SERIAL = "usb01"

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReadResult:
    """Storage class for register read results."""

    def __init__(self, register_words):
        """Init."""
        self.registers = register_words
        self.bits = register_words


@pytest.fixture
def mock_pymodbus():
    """Mock pymodbus."""
    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient",
        return_value=mock_pb,
        autospec=True,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_pb,
        autospec=True,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient",
        return_value=mock_pb,
        autospec=True,
    ):
        yield mock_pb


@pytest.fixture
def check_config_loaded():
    """Set default for check_config_loaded."""
    return True


@pytest.fixture
def register_words():
    """Set default for register_words."""
    return [0x00, 0x00]


@pytest.fixture
def config_addon():
    """Add entra configuration items."""
    return None


@pytest.fixture
def do_exception():
    """Remove side_effect to pymodbus calls."""
    return False


@pytest.fixture
async def mock_modbus(
    hass, caplog, register_words, check_config_loaded, config_addon, do_config
):
    """Load integration modbus using mocked pymodbus."""
    conf = copy.deepcopy(do_config)
    if config_addon:
        for key in conf.keys():
            conf[key][0].update(config_addon)
    caplog.set_level(logging.WARNING)
    config = {
        DOMAIN: [
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: TEST_MODBUS_NAME,
                **conf,
            }
        ]
    }
    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient",
        return_value=mock_pb,
        autospec=True,
    ):
        now = dt_util.utcnow()
        with mock.patch(
            "homeassistant.helpers.event.dt_util.utcnow",
            return_value=now,
            autospec=True,
        ):
            result = await async_setup_component(hass, DOMAIN, config)
            assert result or not check_config_loaded
        await hass.async_block_till_done()
        yield mock_pb


@pytest.fixture
async def mock_pymodbus_exception(hass, do_exception, mock_modbus):
    """Trigger update call with time_changed event."""
    if do_exception:
        exc = ModbusException("fail read_coils")
        mock_modbus.read_coils.side_effect = exc
        mock_modbus.read_discrete_inputs.side_effect = exc
        mock_modbus.read_input_registers.side_effect = exc
        mock_modbus.read_holding_registers.side_effect = exc


@pytest.fixture
async def mock_pymodbus_return(hass, register_words, mock_modbus):
    """Trigger update call with time_changed event."""
    read_result = ReadResult(register_words)
    mock_modbus.read_coils.return_value = read_result
    mock_modbus.read_discrete_inputs.return_value = read_result
    mock_modbus.read_input_registers.return_value = read_result
    mock_modbus.read_holding_registers.return_value = read_result


@pytest.fixture
async def mock_do_cycle(hass, mock_pymodbus_exception, mock_pymodbus_return):
    """Trigger update call with time_changed event."""
    now = dt_util.utcnow() + timedelta(seconds=90)
    with mock.patch(
        "homeassistant.helpers.event.dt_util.utcnow", return_value=now, autospec=True
    ):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()


@pytest.fixture
async def mock_test_state(hass, request):
    """Mock restore cache."""
    mock_restore_cache(hass, request.param)
    return request.param


@pytest.fixture
async def mock_ha(hass, mock_pymodbus_return):
    """Load homeassistant to allow service calls."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
