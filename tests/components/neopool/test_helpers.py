"""Test the NeoPool helpers."""

from modbus_connection import ModbusSerialParams, ModbusTcpParams
import pytest

from homeassistant.components.neopool.helpers import build_modbus_params
from homeassistant.const import CONF_HOST, CONF_PORT


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {CONF_HOST: "192.0.2.1", CONF_PORT: 502, "modbus_framer": "tcp"},
            ModbusTcpParams(host="192.0.2.1", port=502),
        ),
        (
            {CONF_HOST: "192.0.2.1", CONF_PORT: 1502, "modbus_framer": "rtu"},
            ModbusSerialParams(
                device="socket://192.0.2.1:1502", framer="rtu", baudrate=115200
            ),
        ),
        (
            {CONF_HOST: "2001:db8::1", CONF_PORT: 502, "modbus_framer": "rtu"},
            ModbusSerialParams(
                device="socket://[2001:db8::1]:502", framer="rtu", baudrate=115200
            ),
        ),
        (
            {CONF_HOST: "Gateway.Local", CONF_PORT: 502, "modbus_framer": "rtu"},
            ModbusSerialParams(
                device="socket://gateway.local:502", framer="rtu", baudrate=115200
            ),
        ),
    ],
)
def test_build_modbus_params(
    data: dict[str, object],
    expected: ModbusTcpParams | ModbusSerialParams,
) -> None:
    """The connection params map from config data, bracketing IPv6 for serial."""
    assert build_modbus_params(data) == expected
