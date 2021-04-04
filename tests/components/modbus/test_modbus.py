"""The tests for the Modbus sensor component."""
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
)
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.const import (
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
)
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    "do_config",
    [
        {
            DOMAIN: [
                {
                    CONF_TYPE: "tcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "tcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "udp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "udp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "rtuovertcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "rtuovertcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "serial",
                    CONF_BAUDRATE: 9600,
                    CONF_BYTESIZE: 8,
                    CONF_METHOD: "rtu",
                    CONF_PORT: "usb01",
                    CONF_PARITY: "E",
                    CONF_STOPBITS: 1,
                }
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "serial",
                    CONF_BAUDRATE: 9600,
                    CONF_BYTESIZE: 8,
                    CONF_METHOD: "rtu",
                    CONF_PORT: "usb01",
                    CONF_PARITY: "E",
                    CONF_STOPBITS: 1,
                    CONF_NAME: "modbusTest",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                }
            ]
        },
    ],
)
async def test_config_modbus(hass, do_config):
    """Run test for modbus."""

    mock_sync = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_sync
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient", return_value=mock_sync
    ):
        # mocking is needed to secure the pymodbus library is not called!
        assert await async_setup_component(hass, DOMAIN, do_config)
        await hass.async_block_till_done()
        assert DOMAIN in hass.data

        # the "if" should really be in the do_config above, but
        # there are no easy way to have vol add default in a test setup
        if CONF_NAME not in do_config[DOMAIN][0]:
            do_config[DOMAIN][0][CONF_NAME] = DEFAULT_HUB
        assert do_config[DOMAIN][0][CONF_NAME] in hass.data[DOMAIN]


@pytest.mark.parametrize(
    "do_config",
    [
        {
            DOMAIN: [
                {
                    CONF_TYPE: "tcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest1",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                },
                {
                    CONF_TYPE: "tcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest2",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                },
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "tcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest1",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                },
                {
                    CONF_TYPE: "udp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest2",
                    CONF_TIMEOUT: 30,
                    CONF_DELAY: 10,
                },
            ]
        },
        {
            DOMAIN: [
                {
                    CONF_TYPE: "tcp",
                    CONF_HOST: "modbusTestHost",
                    CONF_PORT: 5501,
                    CONF_NAME: "modbusTest1",
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
                    CONF_NAME: "modbusTest2",
                },
            ]
        },
    ],
)
async def test_multiple_config_modbus(hass, do_config):
    """Run test for modbus."""

    mock_sync = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_sync
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient", return_value=mock_sync
    ):
        # mocking is needed to secure the pymodbus library is not called!
        assert await async_setup_component(hass, DOMAIN, do_config)
        await hass.async_block_till_done()
        assert DOMAIN in hass.data

        # the "if" should really be in the do_config above, but
        # there are no easy way to have vol add default.
        assert do_config[DOMAIN][0][CONF_NAME] in hass.data[DOMAIN]
        assert do_config[DOMAIN][1][CONF_NAME] in hass.data[DOMAIN]


@pytest.mark.parametrize(
    "do_read_type",
    [
        "read_coils",
        "read_discrete_inputs",
        "read_input_registers",
        "read_holding_registers",
    ],
)
async def test_pymodbus_read(hass, do_read_type):
    """Run test for modbus."""

    # dummy config
    config_hub = {
        CONF_NAME: DEFAULT_HUB,
        CONF_TYPE: "tcp",
        CONF_HOST: "modbusTest",
        CONF_PORT: 5001,
        CONF_DELAY: 1,
        CONF_TIMEOUT: 1,
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
        # mocking is needed to secure the pymodbus library is not called!
        # simulate read_* functions in pymodbus library

        hub = ModbusHub(config_hub)
        print(hub)


@pytest.mark.parametrize(
    "do_write_type",
    [],
)
async def test_pymodbus_write(hass, do_write_type):
    """Run test for modbus."""


async def test_user_write(hass):
    """Run test for modbus."""
