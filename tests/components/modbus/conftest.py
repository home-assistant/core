"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import DEFAULT_HUB, MODBUS_DOMAIN as DOMAIN
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

from tests.common import async_fire_time_changed

TEST_MODBUS_NAME = "modbusTest"
_LOGGER = logging.getLogger(__name__)


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


@pytest.fixture
async def mock_modbus(hass, mock_pymodbus):
    """Load integration modbus using mocked pymodbus."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
                CONF_NAME: TEST_MODBUS_NAME,
            }
        ]
    }
    assert await async_setup_component(hass, DOMAIN, config) is True
    await hass.async_block_till_done()
    yield mock_pymodbus


class ReadResult:
    """Storage class for register read results."""

    def __init__(self, register_words):
        """Init."""
        self.registers = register_words
        self.bits = register_words


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
    check_config_only=False,
    config_modbus=None,
    scan_interval=None,
    expect_init_to_fail=False,
):
    """Run test on device for given config."""

    if config_modbus is None:
        config_modbus = {
            DOMAIN: {
                CONF_NAME: DEFAULT_HUB,
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTest",
                CONF_PORT: 5001,
            },
        }

    mock_sync = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_sync
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient", return_value=mock_sync
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
            assert await async_setup_component(hass, DOMAIN, config_modbus)
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

        assert DOMAIN in hass.config.components
        if config_device is not None:
            entity_id = f"{entity_domain}.{device_name}"
            device = hass.states.get(entity_id)

            if expect_init_to_fail:
                assert device is None
            elif device is None:
                pytest.fail("CONFIG failed, see output")
        if check_config_only:
            return

        # Trigger update call with time_changed event
        now = now + timedelta(seconds=scan_interval + 60)
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

        # Check state
        entity_id = f"{entity_domain}.{device_name}"
        return hass.states.get(entity_id).state


async def base_config_test(
    hass,
    config_device,
    device_name,
    entity_domain,
    array_name_discovery,
    array_name_old_config,
    method_discovery=False,
    config_modbus=None,
    expect_init_to_fail=False,
):
    """Check config of device for given config."""

    await base_test(
        hass,
        config_device,
        device_name,
        entity_domain,
        array_name_discovery,
        array_name_old_config,
        None,
        None,
        method_discovery=method_discovery,
        check_config_only=True,
        config_modbus=config_modbus,
        expect_init_to_fail=expect_init_to_fail,
    )


async def prepare_service_update(hass, config, entity_id):
    """Run test for service write_coil."""

    config_modbus = {
        DOMAIN: {
            CONF_NAME: DEFAULT_HUB,
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTest",
            CONF_PORT: 5001,
            **config,
        },
    }
    assert await async_setup_component(hass, DOMAIN, config_modbus)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
