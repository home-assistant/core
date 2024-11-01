"""The tests for the Modbus sensor component."""

import copy
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any
from unittest import mock

from freezegun.api import FrozenDateTimeFactory
from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import MODBUS_DOMAIN as DOMAIN, TCP
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_TYPE,
)
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

    def __init__(self, register_words) -> None:
        """Init."""
        self.registers = register_words
        self.bits = register_words
        self.value = register_words

    def isError(self):
        """Set error state."""
        return False


@pytest.fixture(name="check_config_loaded")
def check_config_loaded_fixture():
    """Set default for check_config_loaded."""
    return True


@pytest.fixture(name="register_words")
def register_words_fixture():
    """Set default for register_words."""
    return [0x00, 0x00]


@pytest.fixture(name="config_addon")
def config_addon_fixture() -> dict[str, Any] | None:
    """Add extra configuration items."""
    return None


@pytest.fixture(name="do_exception")
def do_exception_fixture():
    """Remove side_effect to pymodbus calls."""
    return False


@pytest.fixture(name="mock_pymodbus")
def mock_pymodbus_fixture(do_exception, register_words):
    """Mock pymodbus."""
    mock_pb = mock.AsyncMock()
    mock_pb.close = mock.MagicMock()
    read_result = ReadResult(register_words if register_words else [])
    mock_pb.read_coils.return_value = read_result
    mock_pb.read_discrete_inputs.return_value = read_result
    mock_pb.read_input_registers.return_value = read_result
    mock_pb.read_holding_registers.return_value = read_result
    mock_pb.write_register.return_value = read_result
    mock_pb.write_registers.return_value = read_result
    mock_pb.write_coil.return_value = read_result
    mock_pb.write_coils.return_value = read_result
    if do_exception:
        exc = ModbusException("mocked pymodbus exception")
        mock_pb.read_coils.side_effect = exc
        mock_pb.read_discrete_inputs.side_effect = exc
        mock_pb.read_input_registers.side_effect = exc
        mock_pb.read_holding_registers.side_effect = exc
        mock_pb.write_register.side_effect = exc
        mock_pb.write_registers.side_effect = exc
        mock_pb.write_coil.side_effect = exc
        mock_pb.write_coils.side_effect = exc
    with (
        mock.patch(
            "homeassistant.components.modbus.modbus.AsyncModbusTcpClient",
            return_value=mock_pb,
            autospec=True,
        ),
        mock.patch(
            "homeassistant.components.modbus.modbus.AsyncModbusSerialClient",
            return_value=mock_pb,
            autospec=True,
        ),
        mock.patch(
            "homeassistant.components.modbus.modbus.AsyncModbusUdpClient",
            return_value=mock_pb,
            autospec=True,
        ),
    ):
        yield mock_pb


@pytest.fixture(name="mock_modbus")
async def mock_modbus_fixture(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    check_config_loaded,
    config_addon,
    do_config,
    mock_pymodbus,
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
                CONF_SENSORS: [
                    {
                        CONF_NAME: "dummy",
                        CONF_ADDRESS: 9999,
                    }
                ],
                **conf,
            }
        ]
    }
    now = dt_util.utcnow()
    with mock.patch(
        "homeassistant.helpers.event.dt_util.utcnow",
        return_value=now,
        autospec=True,
    ):
        result = await async_setup_component(hass, DOMAIN, config)
        assert result or not check_config_loaded
    await hass.async_block_till_done()
    return mock_pymodbus


@pytest.fixture(name="mock_do_cycle")
async def mock_do_cycle_fixture(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_modbus,
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
async def mock_test_state_fixture(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> Any:
    """Mock restore cache."""
    mock_restore_cache(hass, request.param)
    return request.param


@pytest.fixture(name="mock_modbus_ha")
async def mock_modbus_ha_fixture(
    hass: HomeAssistant, mock_modbus: mock.AsyncMock
) -> mock.AsyncMock:
    """Load homeassistant to allow service calls."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
    return mock_modbus


@pytest.fixture(name="caplog_setup_text")
async def caplog_setup_text_fixture(caplog: pytest.LogCaptureFixture) -> str:
    """Return setup log of integration."""
    return caplog.text
