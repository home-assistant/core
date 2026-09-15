"""Adapt a borrowed ModbusUnit to the sma_modbus library's connection interface.

The ``modbus`` integration hands out a single :class:`~modbus_connection.ModbusUnit`
via :func:`~homeassistant.components.modbus.async_get_unit`. The ``sma_modbus``
library expects a :class:`~modbus_connection.ModbusConnection` with a
``for_unit()`` method that returns distinct units for different unit IDs.

Some SMA devices (e.g. the Sunny Home Manager) serve registers on multiple
Modbus unit IDs.  The borrowed unit is bound to one unit ID, so the adapter
extracts the underlying connection from it and creates fresh unit handles
for each requested ID, all sharing the same TCP socket.
"""

from typing import override

from modbus_connection import ModbusConnection, ModbusUnit
from modbus_connection._client import BaseModbusConnection


class ModbusUnitConnection(BaseModbusConnection):
    """Present a borrowed ``ModbusUnit`` as a ``ModbusConnection``."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Initialize the adapter from a borrowed unit.

        The underlying connection is extracted so ``for_unit()`` can create
        units with different unit IDs on the same socket.
        """
        connection: ModbusConnection = unit._conn  # type: ignore[attr-defined]  # noqa: SLF001
        super().__init__(connection._params)  # noqa: SLF001
        self._connection = connection

    @override
    def for_unit(self, unit_id: int) -> ModbusUnit:
        """Return a unit handle for ``unit_id`` on the shared connection."""
        return self._connection.for_unit(unit_id)

    @override
    async def _connect_client(self) -> object:
        """Delegate to the underlying connection."""
        return await self._connection._connect_client()  # noqa: SLF001

    @override
    async def _close_client(self, client: object) -> None:
        """Delegate to the underlying connection."""
        await self._connection._close_client(client)  # noqa: SLF001
