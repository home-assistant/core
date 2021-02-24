"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    CONF_REGISTER,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
)
from homeassistant.const import (
    CONF_ADDRESS,
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


@pytest.fixture
def config_modbus_server():
    """Fixture to provide a modbus slave configuration."""
    return {
        DOMAIN: {
            CONF_NAME: DEFAULT_HUB,
            CONF_TYPE: "tcpserver",
            CONF_HOST: "modbusTest",
            CONF_PORT: 5001,
        },
    }


class AsyncTcpServerMock:
    """Mock AsyncTcpServer."""

    async def serve_forever(self):
        """Mock serve_forever call."""
        pass

    def __bool__(self):
        """Convert to bool."""
        return True

    def server_close(self):
        """Do nothing."""
        pass

    @property
    def active_connections(self):
        """Return active server connections array."""
        return ["some"]


class MockModbusDataBlock:
    """Mock Modbus data block."""

    def __init__(self):
        """Mock init method."""
        self._values = []

    def getValues(self, address, count):
        """Mock get values method."""
        return self._values

    def setValues(self, address, values):
        """Mock set values method."""
        self._values = values


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

    # Create a server block with the necessary methods
    server_blocks = {config_device.get(CONF_SLAVE, 0): MockModbusDataBlock()}

    with mock.patch(
        "homeassistant.components.modbus.modbus_client.ModbusTcpClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus_client.ModbusSerialClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus_client.ModbusUdpClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus_server.StartTcpServer",
        return_value=AsyncTcpServerMock(),
    ), mock.patch(
        "homeassistant.components.modbus.modbus_server.build_server_blocks",
        return_value=server_blocks,
    ):

        # Setup inputs for the sensor
        read_result = ReadResult(register_words)
        mock_sync.read_coils.return_value = read_result
        mock_sync.read_discrete_inputs.return_value = read_result
        mock_sync.read_input_registers.return_value = read_result
        mock_sync.read_holding_registers.return_value = read_result

        # If slave specified, update the server block
        if CONF_SLAVE in config_device:
            register = config_device.get(CONF_REGISTER, config_device.get(CONF_ADDRESS))
            if register is not None:
                server_blocks[config_device[CONF_SLAVE]].setValues(
                    register, register_words
                )

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

            # Modbus server initialize the server block on the started event
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
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
    )
