"""Tests for Flexit Modbus connection construction."""

from unittest.mock import patch

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.components.flexit.connection import create_modbus_connection
from homeassistant.components.flexit.const import TYPE_SERIAL, TYPE_TCP
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE


def test_create_tcp_connection() -> None:
    """Test creating an unopened TCP connection."""
    params = ModbusTcpParams(host="192.168.1.100", port=5020)

    with patch(
        "homeassistant.components.flexit.connection.ModbusConnection"
    ) as connection:
        create_modbus_connection(
            {CONF_TYPE: TYPE_TCP, CONF_HOST: "192.168.1.100", CONF_PORT: 5020}
        )

    connection.assert_called_once_with(params)


def test_create_serial_connection() -> None:
    """Test creating an unopened serial connection."""
    params = ModbusSerialParams(
        device="/dev/ttyUSB0",
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1,
    )

    with patch(
        "homeassistant.components.flexit.connection.ModbusConnection"
    ) as connection:
        create_modbus_connection(
            {
                CONF_TYPE: TYPE_SERIAL,
                CONF_DEVICE: "/dev/ttyUSB0",
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
            }
        )

    connection.assert_called_once_with(params)
