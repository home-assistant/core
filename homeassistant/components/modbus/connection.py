"""Hand out Modbus units over connections shared between integrations."""

from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
from typing import Any

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
def _async_acquire(
    hass: HomeAssistant, params: ModbusParams
) -> tuple[ModbusConnection, Callable[[], Coroutine[Any, Any, None]]]:
    """Take a hold on the connection these credentials describe.

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

    async def release() -> None:
        """Give up this hold, closing behind the last one."""
        shared.consumers -= 1
        if shared.consumers or connections.get(endpoint) is not shared:
            return
        del connections[endpoint]
        _LOGGER.debug("Closing the Modbus connection to %s", endpoint)
        await shared.connection.close()

    return shared.connection, release


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
    connection, release = _async_acquire(hass, params)
    entry.async_on_unload(release)
    return connection.for_unit(unit_id)


@asynccontextmanager
async def async_get_temporary_unit(
    hass: HomeAssistant,
    params: ModbusParams,
    unit_id: int,
) -> AsyncIterator[ModbusUnit]:
    """Hold a unit on the connection these credentials describe for the context.

    For config flows, which have no config entry yet to tie a hold to. A
    connection already held by a config entry is shared and stays up; one
    opened here is closed on exit.

    Raises `HomeAssistantError` if the device is already in use over different
    link settings, which cannot both be honoured on one connection.
    """
    connection, release = _async_acquire(hass, params)
    try:
        yield connection.for_unit(unit_id)
    finally:
        await release()
