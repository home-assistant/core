"""Helper functions for the NeoPool integration."""

from collections.abc import Mapping
import datetime
from typing import Any, Literal

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from neopool_modbus.decoders import encode_device_time
from neopool_modbus.registers import framer_to_socket_name

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .const import CONF_MODBUS_FRAMER, DEFAULT_PORT


def prepare_device_time(hass: HomeAssistant) -> int:
    """Return the unix timestamp the device should display as local wall-clock."""
    tz = dt_util.get_time_zone(hass.config.time_zone) or datetime.UTC
    return encode_device_time(dt_util.now(tz))


def build_modbus_params(
    data: Mapping[str, Any],
) -> ModbusTcpParams | ModbusSerialParams:
    """Build the shared-connection link parameters from config entry data.

    A Modbus TCP link is always MBAP-framed, so it uses ModbusTcpParams with
    the framer omitted (passing it is deprecated). RTU/ASCII framing over a
    socket is a serial link reached through a socket:// device, so it uses
    ModbusSerialParams directly; that is what the modbus integration would
    canonicalise an RTU ModbusTcpParams to anyway, built here to avoid the
    deprecation warning. The baud rate only sets the inter-frame timing for the
    socket-carried serial framing; 19200 is NeoPool's RS485 rate.
    """
    host = data[CONF_HOST]
    port = data.get(CONF_PORT, DEFAULT_PORT)
    framer = framer_to_socket_name(data.get(CONF_MODBUS_FRAMER, "tcp"))
    if framer == "socket":
        return ModbusTcpParams(host=host, port=port)
    # An IPv6 literal must be bracketed, or its colons read as the port separator.
    device_host = f"[{host}]" if ":" in host else host
    serial_framer: Literal["rtu", "ascii"] = "ascii" if framer == "ascii" else "rtu"
    return ModbusSerialParams(
        device=f"socket://{device_host}:{port}", framer=serial_framer, baudrate=19200
    )
