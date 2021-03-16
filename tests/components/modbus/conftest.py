"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import (
    CONF_TYPE_TCPSERVER,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
)
from homeassistant.components.modbus.modbus_slave import ModbusSlavesHolder
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


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
    mock_hook=None,
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
    # Setup inputs for the sensor
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_sync
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient", return_value=mock_sync
    ):

        read_result = (
            ReadResult(register_words)
            if register_words
            else ModbusException("Emulate Modbus read exception")
        )
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

            if config_modbus[DOMAIN][CONF_TYPE] == CONF_TYPE_TCPSERVER:
                hass.bus.fire(EVENT_HOMEASSISTANT_STARTED, {})

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

        assert DOMAIN in hass.data
        if config_device is not None:
            entity_id = f"{entity_domain}.{device_name}"
            device = hass.states.get(entity_id)
            if device is None:
                pytest.fail("CONFIG failed, see output")
        if check_config_only:
            return

        # Trigger update call with time_changed event
        now = now + timedelta(seconds=scan_interval + 60)
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

        # mock_hook may also call an arbitrary service
        # Then the resulting state will hold the desired state
        if mock_hook is not None:
            await mock_hook(mock_sync)
            await hass.async_block_till_done()

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
    )


async def server_test(
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
    mock_hook=None,
):
    """Configure Modbus TCP Server for testing using base_test."""

    mock_value = mock.AsyncMock()
    # Modbus server _ensure_connected throws exception if no client
    # connected to the modbus server making sensor or switch unavailable
    # setting to the non-empty array emulates the connected client
    mock_value.active_connections = ["connection"]
    mock_value.server_close.not_async = True

    # emulate ModbusDataBlock, holding the register values
    data_block = mock.MagicMock()
    data_block.getValues.return_value = register_words

    # emulate the SlavesHolder::build_server_blocks()
    blocks = mock.MagicMock()
    blocks.return_value = {config_device.get(CONF_SLAVE, 0): data_block}

    with mock.patch.object(
        ModbusSlavesHolder,
        "build_server_blocks",
        blocks,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.StartTcpServer"
    ) as mock_server:
        mock_server.return_value = mock_value
        state = await base_test(
            hass,
            config_device,
            device_name,
            entity_domain,
            array_name_discovery,
            array_name_old_config,
            register_words,
            expected,
            method_discovery,
            check_config_only,
            config_modbus,
            scan_interval,
            mock_hook,
        )
        mock_server.assert_called_once()
    return state, data_block


@pytest.fixture
def config_modbus_server():
    """Fixture to provide a modbus slave configuration."""
    return {
        DOMAIN: {
            CONF_NAME: DEFAULT_HUB,
            CONF_TYPE: CONF_TYPE_TCPSERVER,
            CONF_HOST: "modbusTest",
            CONF_PORT: 5001,
        },
    }
