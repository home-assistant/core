"""Helper functions for the NeoPool integration."""

from collections.abc import Mapping
import datetime as dt
from typing import Any, Literal

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from neopool_modbus.decoders import encode_device_time
from neopool_modbus.registers import framer_to_socket_name

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .const import (
    CONF_BAUDRATE,
    CONF_MODBUS_FRAMER,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    TYPE_SERIAL,
    TYPE_TCP,
)


def prepare_device_time(hass: HomeAssistant) -> int:
    """Return the unix timestamp the device should display as local wall-clock."""
    tz = dt_util.get_time_zone(hass.config.time_zone) or dt.UTC
    return encode_device_time(dt_util.now(tz))


def _normalize_host(host: str) -> str:
    """Fold the host to lower case, matching ModbusTcpParams.

    ModbusTcpParams lower-cases the host it is given, so a TCP endpoint dedupes
    regardless of case. The socket:// device string an RTU/ASCII link builds has
    to be folded the same way, or Device.local and device.local would open two
    links to one gateway. An IPv6 scope id after a % is left untouched.
    """
    address, separator, scope = host.partition("%")
    return address.lower() + separator + scope


def build_modbus_params(
    data: Mapping[str, Any],
) -> ModbusTcpParams | ModbusSerialParams:
    """Build the shared-connection link parameters from config entry data.

    RTU/ASCII over a socket (an ESPHome stream-server gateway) is built as
    ModbusSerialParams, not ModbusTcpParams with a framer (deprecated); its baud
    rate is the modbus integration's canonical 115200 so a shared gateway
    compares equal. A missing CONF_TYPE predates the connection-type choice and
    reads as a network (TCP) entry.
    """
    if data.get(CONF_TYPE, TYPE_TCP) == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
            framer="rtu",
        )
    host = _normalize_host(data[CONF_HOST])
    port = data.get(CONF_PORT, DEFAULT_PORT)
    framer = framer_to_socket_name(data.get(CONF_MODBUS_FRAMER, "tcp"))
    if framer == "socket":
        return ModbusTcpParams(host=host, port=port)
    # An IPv6 literal must be bracketed, or its colons read as the port separator.
    device_host = f"[{host}]" if ":" in host else host
    serial_framer: Literal["rtu", "ascii"] = "ascii" if framer == "ascii" else "rtu"
    return ModbusSerialParams(
        device=f"socket://{device_host}:{port}", framer=serial_framer, baudrate=115200
    )
