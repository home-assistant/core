"""Adapt a borrowed ModbusUnit to the sma_modbus library's connection interface.

The ``modbus`` integration hands out a single :class:`~modbus_connection.ModbusUnit`
via :func:`~homeassistant.components.modbus.async_get_unit`. The ``sma_modbus``
library expects a :class:`~modbus_connection.ModbusConnection` with a
``for_unit()`` method. This thin wrapper bridges the gap so the library can
open unit handles on the shared connection.
"""

from modbus_connection import ModbusUnit


class ModbusUnitConnection:
    """Present a borrowed ``ModbusUnit`` as a ``ModbusConnection``."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Initialize the adapter."""
        self._unit = unit

    def for_unit(self, unit_id: int) -> ModbusUnit:
        """Return the borrowed unit for any requested unit ID."""
        return self._unit
