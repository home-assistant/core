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

from modbus_connection import ModbusConnection, ModbusUnit


class ModbusUnitConnection:
    """Present a borrowed ``ModbusUnit`` as a ``ModbusConnection``."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Initialize the adapter from a borrowed unit.

        The underlying connection is extracted so ``for_unit()`` can create
        units with different unit IDs on the same socket.
        """
        self._connection: ModbusConnection = unit._conn  # noqa: SLF001

    def for_unit(self, unit_id: int) -> ModbusUnit:
        """Return a unit handle for ``unit_id`` on the shared connection."""
        return self._connection.for_unit(unit_id)
