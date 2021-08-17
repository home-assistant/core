"""Base class to integrate different implementation of enocean over modbus protocol."""


class ModbusEnoceanAdapter:
    """Base class to integrate different implementation of enocean over modbus protocol."""

    identifier: str

    async def read(self, size: int = 1) -> bytearray:
        """Read number of byes from enocean adapter, needs be be overwritten."""

    async def write(self, value: bytearray) -> None:
        """Write value to enocean adapter, needs be be overwritten."""
