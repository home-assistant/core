"""Helper functions for the NeoPool integration."""

from collections.abc import Mapping
import datetime
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
    tz = dt_util.get_time_zone(hass.config.time_zone) or datetime.UTC
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

    A direct serial link uses ModbusSerialParams on the device path; NeoPool
    RS485 is RTU-framed at 8N1 (the library default), so only the baud rate is
    carried. The baud rate sets the serial inter-frame timing; 19200 is NeoPool's
    RS485 rate, giving the spec's 3.5-character gap (~2 ms) for that line.

    Otherwise the link is reached over the network. A Modbus TCP link is always
    MBAP-framed, so it uses ModbusTcpParams with the framer omitted (passing
    it is deprecated). RTU/ASCII framing over a socket (an ESPHome stream-server
    gateway) is a serial link reached through a socket:// device, so it uses
    ModbusSerialParams directly; that is what the modbus integration would
    canonicalise an RTU ModbusTcpParams to anyway, built here to avoid the
    deprecation warning. Its baud rate matches the modbus integration's
    canonical 115200, so consumers sharing a gateway compare equal.

    Entries predating the connection-type choice carry no CONF_TYPE; they are
    all network entries, so a missing type reads as TCP.
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
