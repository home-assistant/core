"""The tests for the Modbus sensor component."""
from dataclasses import dataclass
from datetime import timedelta
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import (
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
    TCP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
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
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_pb,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient", return_value=mock_pb
    ):
        yield mock_pb


@pytest.fixture(
    params=[
        {"testLoad": True},
    ],
)
async def mock_modbus(hass, caplog, request, do_config):
    """Load integration modbus using mocked pymodbus."""

    caplog.set_level(logging.WARNING)
    config = {
        DOMAIN: [
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: TEST_MODBUS_NAME,
                **do_config,
            }
        ]
    }
    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        mock_pb.read_coils.return_value = ReadResult([0x00])
        read_result = ReadResult([0x00, 0x00])
        mock_pb.read_discrete_inputs.return_value = read_result
        mock_pb.read_input_registers.return_value = read_result
        mock_pb.read_holding_registers.return_value = read_result
        if request.param["testLoad"]:
            assert await async_setup_component(hass, DOMAIN, config) is True
        else:
            await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield mock_pb


@pytest.fixture
async def mock_test_state(hass, request):
    """Mock restore cache."""
    mock_restore_cache(hass, request.param)
    return request.param


@pytest.fixture
async def mock_ha(hass):
    """Load homeassistant to allow service calls."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

@pytest.fixture
async def mock_pymodbus_return(hass, register_words, mock_modbus):
    """Trigger update call with time_changed event."""
    read_result = ReadResult(register_words)
    mock_modbus.read_coils.return_value = read_result
    mock_modbus.read_discrete_inputs.return_value = read_result
    mock_modbus.read_input_registers.return_value = read_result
    mock_modbus.read_holding_registers.return_value = read_result

async def base_test(
    hass,
    config_device,
    device_name,
    entity_domain,
    array_name_discovery,
    array_name_old_config,
    register_words,
    expected,
    method_discovery=False,
    config_modbus=None,
    scan_interval=None,
    expect_init_to_fail=False,
    expect_setup_to_fail=False,
):
    """Run test on device for given config."""

    if config_modbus is None:
        config_modbus = {
            DOMAIN: {
                CONF_NAME: DEFAULT_HUB,
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
            },
        }

    mock_sync = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient",
        autospec=True,
        return_value=mock_sync,
    ):

        # Setup inputs for the sensor
        if register_words is None:
            mock_sync.read_coils.side_effect = ModbusException("fail read_coils")
            mock_sync.read_discrete_inputs.side_effect = ModbusException(
                "fail read_coils"
            )
            mock_sync.read_input_registers.side_effect = ModbusException(
                "fail read_coils"
            )
            mock_sync.read_holding_registers.side_effect = ModbusException(
                "fail read_coils"
            )
        else:
            read_result = ReadResult(register_words)
            mock_sync.read_coils.return_value = read_result
            mock_sync.read_discrete_inputs.return_value = read_result
            mock_sync.read_input_registers.return_value = read_result
            mock_sync.read_holding_registers.return_value = read_result

        # mock timer and add old/new config
        now = dt_util.utcnow()
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            if method_discovery and config_device is not None:
                # setup modbus which in turn does setup for the devices
                config_modbus[DOMAIN].update(
                    {array_name_discovery: [{**config_device}]}
                )
                config_device = None
            assert (
                await async_setup_component(hass, DOMAIN, config_modbus)
                is not expect_setup_to_fail
            )
            await hass.async_block_till_done()

            # setup platform old style
            if config_device is not None:
                config_device = {
                    entity_domain: {
                        CONF_PLATFORM: DOMAIN,
                        array_name_old_config: [
                            {
                                **config_device,
                            }
                        ],
                    }
                }
                if scan_interval is not None:
                    config_device[entity_domain][CONF_SCAN_INTERVAL] = scan_interval
                assert await async_setup_component(hass, entity_domain, config_device)
                await hass.async_block_till_done()

        assert (DOMAIN in hass.config.components) is not expect_setup_to_fail
        if config_device is not None:
            entity_id = f"{entity_domain}.{device_name}"
            device = hass.states.get(entity_id)

            if expect_init_to_fail:
                assert device is None
            elif device is None:
                pytest.fail("CONFIG failed, see output")

        # Trigger update call with time_changed event
        now = now + timedelta(seconds=scan_interval + 60)
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

        # Check state
        entity_id = f"{entity_domain}.{device_name}"
        return hass.states.get(entity_id).state
