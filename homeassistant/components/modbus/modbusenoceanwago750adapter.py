# mypy: allow-untyped-defs, allow-untyped-calls
"""Representation of an wago 750 series enocean modbus adapter."""
import asyncio
import logging
import queue
from typing import Any

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTER,
)

from .modbus import ModbusHub
from .modbusenoceanadapter import ModbusEnoceanAdapter

_LOGGER = logging.getLogger("enocean.communicators.ModbusEnOceanWago750Adapter")


class ModbusEnOceanWago750Adapter(ModbusEnoceanAdapter):
    """Adapter implementing enocean over modbus protocol for wao 750 series."""

    identifier: str = "wago_750_modbus_enocean"

    def __init__(
        self, hub: ModbusHub, slave: Any, input_address: int, output_address: int
    ):
        """Initialize Wago750365ModbusEnOceanAdapter."""
        self._hub = hub
        self._slave = slave
        self._input_address = input_address
        self._output_address = output_address
        self.receive: queue.Queue = queue.Queue()

    async def read(self, size: int = 1) -> bytearray:
        """Read number of bytes from enocean adapter."""
        result = bytearray(size)
        for i in range(size):
            _LOGGER.debug("enocean read byte=%s of size=%s", i, size)
            result[i : i + 1] = await self.readNextByte()

        _LOGGER.debug("enocean read complete=%s", result)
        return result

    async def readNextByte(self) -> Any:
        """Read next byte."""
        if self.receive.empty():
            bytes = await self.readNextBytesFromHub()
            _LOGGER.debug("enocean received result from hub, size=%s", len(bytes))
            for i in range(len(bytes)):
                self.receive.put(bytes[i : i + 1])
        _LOGGER.debug("enocean readNextByte, buffer size=%s", self.receive.qsize())
        return self.receive.get()

    async def readNextBytesFromHub(self) -> bytearray:
        """Read up to 3 bytes from modbus enocean control."""
        control: Any = None
        control_byte: int = 0
        control_byte_on: int = 0
        status_byte: int = 0
        status_byte_on: int = 0
        status: Any = None
        control_register1_bytes: bytearray
        register_1_bytes: bytearray
        _LOGGER.debug("enocean read next byte from hub")

        # Wait until control and status bytes are in synch
        while status_byte_on == control_byte_on:
            await asyncio.sleep(0.1)

            # read control register
            control = await self._hub.async_pymodbus_call(
                self._slave, self._output_address, 2, CALL_TYPE_REGISTER_HOLDING
            )
            if control is None:
                return bytearray()

            control_register1_bytes = control.registers[0].to_bytes(2, byteorder="big")
            control_byte = control_register1_bytes[1]
            control_byte_on = (control_byte & 0x02) >> 1

            # read status bit
            status = await self._hub.async_pymodbus_call(
                self._slave, self._input_address, 2, CALL_TYPE_REGISTER_INPUT
            )
            if status is None:
                return bytearray()
            register_1_bytes = status.registers[0].to_bytes(2, byteorder="big")
            status_byte = register_1_bytes[1]
            status_byte_on = (status_byte & 0x02) >> 1

        # Read size of bytes available
        size = (status_byte & 0x38) >> 3

        _LOGGER.debug("Read enocean number of bytes=%s", size)
        if size < 0 or size > 3:
            _LOGGER.warning("Unsupported size of message received: size=%s", size)
            return bytearray()

        result = bytearray(size)
        # ready to read input
        if size > 0:
            result[0] = register_1_bytes[0]

            if size > 1 and len(status.registers) > 1:
                register_2_bytes = status.registers[1].to_bytes(2, byteorder="big")
                result[1] = register_2_bytes[1]

                if size > 2:
                    result[2] = register_2_bytes[0]

        # Ack reading
        _LOGGER.debug(
            "Status of enocean control register s=%s, result=%s", control, result
        )
        bytes = bytearray(2)
        bytes[0] = control_register1_bytes[0]
        bytes[1] = control_register1_bytes[1] & 0xFD | control_register1_bytes[1] ^ 0x02
        await self._hub.async_pymodbus_call(
            self._slave,
            self._output_address,
            int.from_bytes(bytes, byteorder="big", signed=False),
            CALL_TYPE_WRITE_REGISTER,
        )

        _LOGGER.debug("enocean result=%s", result)

        return result

    async def write(self, value: bytearray) -> None:
        """Write value to enocean adapter, not supported by this module."""
        _LOGGER.warn(
            "Sending values to EnOcean devices not supported by WAGO modbus adapter."
        )
