"""Hand out Modbus units over connections shared between integrations."""

from dataclasses import dataclass
import logging

from modbus_connection import (
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTlsParams,
    ModbusUdpParams,
    ModbusUnit,
)
from modbus_connection.tmodbus import ModbusConnection

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type ModbusParams = (
    ModbusTcpParams | ModbusUdpParams | ModbusTlsParams | ModbusSerialParams
)
type ModbusEndpoint = tuple[str, str, int] | tuple[str, str]

DATA_MODBUS_CONNECTIONS: HassKey[dict[ModbusEndpoint, _SharedConnection]] = HassKey(
    f"{DOMAIN}_connections"
)


@dataclass
class _SharedConnection:
    """A connection and how many units are held on it."""

    params: ModbusParams
    connection: ModbusConnection
    consumers: int = 0


@callback
def async_get_unit(
    hass: HomeAssistant,
    entry: ConfigEntry,
    params: ModbusParams,
    unit_id: int,
) -> ModbusUnit:
    """Return a unit on the connection these credentials describe.

    Consumers of one device share a connection, so their requests serialize
    behind its lock. It is closed when the last config entry holding a unit on
    it unloads.

    Raises `HomeAssistantError` if the device is already in use over different
    link settings, which cannot both be honoured on one connection.
    """
    endpoint = params.endpoint
    connections = hass.data.setdefault(DATA_MODBUS_CONNECTIONS, {})
    if (shared := connections.get(endpoint)) is None:
        shared = connections[endpoint] = _SharedConnection(
            params, ModbusConnection(params)
        )
    elif shared.params != params:
        raise HomeAssistantError(
            f"Modbus device {endpoint} is already in use with different link "
            f"settings: {shared.params} against {params}"
        )

    shared.consumers += 1

    async def _release() -> None:
        """Give up this hold, closing behind the last one."""
        shared.consumers -= 1
        if shared.consumers or connections.get(endpoint) is not shared:
            return
        del connections[endpoint]
        _LOGGER.debug("Closing the Modbus connection to %s", endpoint)
        await shared.connection.close()

    entry.async_on_unload(_release)
    return shared.connection.for_unit(unit_id)
