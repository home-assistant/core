"""Hand out Modbus units over connections shared between integrations."""

from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
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
    """A connection and the units held on it."""

    params: ModbusParams
    connection: ModbusConnection
    units: dict[str, set[int]] = field(default_factory=dict)
    """The unit ids each config entry holds, keyed by entry id."""
    transient: int = 0
    """Holds with no config entry behind them, taken by a config flow."""

    @property
    def consumers(self) -> int:
        """How many holds are on this connection."""
        return sum(len(held) for held in self.units.values()) + self.transient


@dataclass(frozen=True, kw_only=True)
class ModbusConnectionInfo:
    """A connection the integration is keeping open, and who is using it."""

    endpoint: ModbusEndpoint
    connected: bool
    units: dict[str, list[int]]
    """The unit ids each config entry holds, keyed by entry id."""


@callback
def _async_acquire(
    hass: HomeAssistant,
    params: ModbusParams,
    entry_id: str | None,
    unit_id: int,
) -> tuple[ModbusConnection, Callable[[], Coroutine[Any, Any, None]]]:
    """Take a hold on the connection these credentials describe.

    A hold with no ``entry_id`` behind it is a config flow's, which keeps the
    connection up without belonging to anything that could be shown as using
    it.

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

    if entry_id is None:
        shared.transient += 1
    else:
        shared.units.setdefault(entry_id, set()).add(unit_id)

    async def release() -> None:
        """Give up this hold, closing behind the last one."""
        if entry_id is None:
            shared.transient -= 1
        elif (held := shared.units.get(entry_id)) is not None:
            held.discard(unit_id)
            if not held:
                del shared.units[entry_id]
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
    connection, release = _async_acquire(hass, params, entry.entry_id, unit_id)
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
    connection, release = _async_acquire(hass, params, None, unit_id)
    try:
        yield connection.for_unit(unit_id)
    finally:
        await release()


@callback
def async_get_connection_info(hass: HomeAssistant) -> list[ModbusConnectionInfo]:
    """Return the connections the integration is keeping open.

    One entry per physical device, naming the config entries holding units on
    it. A device several integrations share appears once, with all of them. A
    connection a config flow is only probing is not one of them.
    """
    return [
        ModbusConnectionInfo(
            endpoint=endpoint,
            connected=shared.connection.connected,
            units={entry_id: sorted(held) for entry_id, held in shared.units.items()},
        )
        for endpoint, shared in hass.data.get(DATA_MODBUS_CONNECTIONS, {}).items()
        # A connection held only by a config flow's probe is a device nobody
        # has accepted yet, so it is not one of the integration's connections.
        if shared.units
    ]
