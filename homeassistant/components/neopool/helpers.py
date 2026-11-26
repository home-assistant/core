"""Helper functions for the NeoPool integration."""

from collections.abc import Mapping
import datetime as dt
import re
from typing import Any, Literal

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from neopool_modbus.decoders import encode_device_time
from neopool_modbus.registers import aux_relay_available, framer_to_socket_name

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .const import (
    CONF_BAUDRATE,
    CONF_MODBUS_FRAMER,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    TYPE_SERIAL,
    TYPE_TCP,
)

# AUX relay number embedded in an entity unique_id, e.g. "..._aux1" or
# "..._relay_aux2b_period". All AUX entity keys carry an "aux<n>" token.
_AUX_UNIQUE_ID_RE = re.compile(r"aux([1-4])")


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


def cleanup_occupied_aux_entities(
    hass: HomeAssistant,
    entry_id: str,
    platform: str,
    data: Mapping[str, Any],
) -> None:
    """Remove disabled registry entries for AUX relays claimed by a function.

    An AUX whose physical relay the device has assigned to a built-in function
    is no longer created (supported_fn gates it out). On an existing install its
    registry entry would otherwise linger as a restored, unavailable entity.
    Only disabled entries are removed, so a user-enabled AUX that later becomes
    occupied keeps its customisations; the relay assignment is reversible on the
    device.
    """
    registry = er.async_get(hass)
    for entry in registry.entities.get_entries_for_config_entry_id(entry_id):
        if entry.domain != platform or not entry.disabled:
            continue
        match = _AUX_UNIQUE_ID_RE.search(entry.unique_id)
        if match and not aux_relay_available(int(match.group(1)), data):
            registry.async_remove(entry.entity_id)
