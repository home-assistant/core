"""The tests for the Modbus init."""
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
import pytest
import voluptuous as vol

from homeassistant.components.modbus import number
from homeassistant.components.modbus.const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_STATE,
    ATTR_UNIT,
    ATTR_VALUE,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
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


async def test_pb_service_write_register(hass):
    """Run test for service write_register."""

    conf_name = "myModbus"
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
                CONF_NAME: conf_name,
            }
        ]
    }

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()

        data = {ATTR_HUB: conf_name, ATTR_UNIT: 17, ATTR_ADDRESS: 16, ATTR_VALUE: 15}
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True
        )
        assert mock_pb.write_register.called
        assert mock_pb.write_register.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_VALUE],
        )
        mock_pb.write_register.side_effect = ModbusException("fail write_")
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True
        )

        data[ATTR_VALUE] = [1, 2, 3]
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True
        )
        assert mock_pb.write_registers.called
        assert mock_pb.write_registers.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_VALUE],
        )
        mock_pb.write_registers.side_effect = ModbusException("fail write_")
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True
        )


async def test_pb_service_write_coil(hass, caplog):
    """Run test for service write_coil."""

    conf_name = "myModbus"
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
                CONF_NAME: conf_name,
            }
        ]
    }

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()

        data = {ATTR_HUB: conf_name, ATTR_UNIT: 17, ATTR_ADDRESS: 16, ATTR_STATE: False}
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
        assert mock_pb.write_coil.called
        assert mock_pb.write_coil.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_STATE],
        )
        mock_pb.write_coil.side_effect = ModbusException("fail write_")
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)

        data[ATTR_STATE] = [True, False, True]
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
        assert mock_pb.write_coils.called
        assert mock_pb.write_coils.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_STATE],
        )

        caplog.set_level(logging.DEBUG)
        caplog.clear
        mock_pb.write_coils.side_effect = ModbusException("fail write_")
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
        assert caplog.records[-1].levelname == "ERROR"
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
        assert caplog.records[-1].levelname == "DEBUG"


async def test_pymodbus_constructor_fail(hass, caplog):
    """Run test for failing pymodbus constructor."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
            }
        ]
    }
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient"
    ) as mock_pb:
        caplog.set_level(logging.ERROR)
        mock_pb.side_effect = ModbusException("test no class")
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert mock_pb.called


async def test_pymodbus_connect_fail(hass, caplog):
    """Run test for failing pymodbus constructor."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
            }
        ]
    }
    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        caplog.set_level(logging.ERROR)
        mock_pb.connect.side_effect = ModbusException("test connect fail")
        mock_pb.close.side_effect = ModbusException("test connect fail")
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
