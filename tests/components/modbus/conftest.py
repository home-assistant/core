"""The tests for the Modbus sensor component."""
import copy
from dataclasses import dataclass
from datetime import timedelta
import logging
from unittest import mock

from freezegun.api import FrozenDateTimeFactory
from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import MODBUS_DOMAIN as DOMAIN, TCP
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, mock_restore_cache

TEST_MODBUS_NAME = "modbusTest"
TEST_ENTITY_NAME = "test entity"
TEST_MODBUS_HOST = "modbusHost"
TEST_PORT_TCP = 5501
TEST_PORT_SERIAL = "usb01"


@dataclass
class ReadResult:
    """Storage class for register read results."""

    def __init__(self, register_words):
        """Init."""
        self.registers = register_words
        self.bits = register_words
        self.value = register_words

    def isError(self):
        """Set error state."""
        return False


@pytest.fixture(name="mock_pymodbus")
def mock_pymodbus_fixture():
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


@pytest.fixture(name="check_config_loaded")
def check_config_loaded_fixture():
    """Set default for check_config_loaded."""
    return True


@pytest.fixture(name="register_words")
def register_words_fixture():
    """Set default for register_words."""
    return [0x00, 0x00]


@pytest.fixture(name="config_addon")
def config_addon_fixture():
    """Add entra configuration items."""
    return None


@pytest.fixture(name="do_exception")
def do_exception_fixture():
    """Remove side_effect to pymodbus calls."""
    return False


@pytest.fixture(name="mock_modbus")
async def mock_modbus_fixture(
    hass, caplog, register_words, check_config_loaded, config_addon, do_config
):
    """Load integration modbus using mocked pymodbus."""
    conf = copy.deepcopy(do_config)
    for key in conf:
        if config_addon:
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


@pytest.fixture(name="mock_pymodbus_exception")
async def mock_pymodbus_exception_fixture(hass, do_exception, mock_modbus):
    """Trigger update call with time_changed event."""
    if do_exception:
        exc = ModbusException("fail read_coils")
        mock_modbus.read_coils.side_effect = exc
        mock_modbus.read_discrete_inputs.side_effect = exc
        mock_modbus.read_input_registers.side_effect = exc
        mock_modbus.read_holding_registers.side_effect = exc


@pytest.fixture(name="mock_pymodbus_return")
async def mock_pymodbus_return_fixture(hass, register_words, mock_modbus):
    """Trigger update call with time_changed event."""
    read_result = ReadResult(register_words) if register_words else None
    mock_modbus.read_coils.return_value = read_result
    mock_modbus.read_discrete_inputs.return_value = read_result
    mock_modbus.read_input_registers.return_value = read_result
    mock_modbus.read_holding_registers.return_value = read_result
    mock_modbus.write_register.return_value = read_result
    mock_modbus.write_registers.return_value = read_result
    mock_modbus.write_coil.return_value = read_result
    mock_modbus.write_coils.return_value = read_result


@pytest.fixture(name="mock_do_cycle")
async def mock_do_cycle_fixture(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_pymodbus_exception,
    mock_pymodbus_return,
) -> FrozenDateTimeFactory:
    """Trigger update call with time_changed event."""
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    return freezer


async def do_next_cycle(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, cycle: int
) -> None:
    """Trigger update call with time_changed event."""
    freezer.tick(timedelta(seconds=cycle))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture(name="mock_test_state")
async def mock_test_state_fixture(hass, request):
    """Mock restore cache."""
    mock_restore_cache(hass, request.param)
    return request.param


@pytest.fixture(name="mock_ha")
async def mock_ha_fixture(hass, mock_pymodbus_return):
    """Load homeassistant to allow service calls."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


@pytest.fixture(name="caplog_setup_text")
async def caplog_setup_text_fixture(caplog):
    """Return setup log of integration."""
    return caplog.text
