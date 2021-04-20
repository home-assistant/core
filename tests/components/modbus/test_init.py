"""The tests for the Modbus init."""
import logging
from unittest import mock

import pytest
import voluptuous as vol

from homeassistant.components.modbus import number
from homeassistant.components.modbus.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    MODBUS_DOMAIN as DOMAIN,
)
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
    "value,value_type",
    [
        (15, int),
        (15.1, float),
        ("15", int),
        ("15.1", float),
        (-15, int),
        (-15.1, float),
        ("-15", int),
        ("-15.1", float),
    ],
)
async def test_number_validator(value, value_type):
    """Test number validator."""

    assert isinstance(number(value), value_type)


async def test_number_exception():
    """Test number exception."""

    try:
        number("x15.1")
    except (vol.Invalid):
        return

    pytest.fail("Number not throwing exception")


async def _config_helper(hass, do_config):
    """Run test for modbus."""

    config = {DOMAIN: do_config}

    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient"
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient"
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient"
    ):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest",
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
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
    ],
)
async def test_config_modbus(hass, caplog, do_config):
    """Run test for modbus."""

    caplog.set_level(logging.ERROR)
    await _config_helper(hass, do_config)
    assert DOMAIN in hass.config.components
    assert len(caplog.records) == 0


async def test_config_multiple_modbus(hass, caplog):
    """Run test for multiple modbus."""

    do_config = [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest1",
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest2",
        },
        {
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_NAME: "modbusTest3",
        },
    ]

    caplog.set_level(logging.ERROR)
    await _config_helper(hass, do_config)
    assert DOMAIN in hass.config.components
    assert len(caplog.records) == 0
