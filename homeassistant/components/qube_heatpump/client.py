"""Qube Heat Pump Client Library."""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import socket
import struct
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse


class QubeClient:
    """Qube Heat Pump Client."""

    def __init__(
        self,
        host: str,
        port: int,
        unit_id: int = 1,
    ) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._unit = unit_id
        self._client: AsyncModbusTcpClient | None = None
        self._io_timeout_s: float = 3.0

    @property
    def host(self) -> str:
        """Return host."""
        return self._host

    @property
    def port(self) -> int:
        """Return port."""
        return self._port

    @property
    def unit(self) -> int:
        """Return unit ID."""
        return self._unit

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self._unit = int(unit_id)

    async def connect(self) -> bool:
        """Connect to the Modbus server."""
        if self._client is None:
            self._client = AsyncModbusTcpClient(self._host, port=self._port)

        if self.is_connected:
            return True

        try:
            return await asyncio.wait_for(
                self._client.connect(), timeout=self._io_timeout_s
            )
        except Exception as exc:  # pylint: disable=broad-except  # noqa: BLE001
            logging.getLogger(__name__).debug("Failed to connect: %s", exc)
            return False

    @property
    def is_connected(self) -> bool:
        """Return True if connected."""
        return bool(self._client and getattr(self._client, "connected", False))

    async def close(self) -> None:
        """Close the connection."""
        if self._client:
            with contextlib.suppress(Exception):
                self._client.close()
            self._client = None

    async def _call(self, method: str, **kwargs: Any) -> Any:
        if self._client is None:
            raise ModbusException("Client not connected")
        func = getattr(self._client, method)
        # Try with 'slave' then 'unit', finally without either
        try:
            resp = await asyncio.wait_for(
                func(**{**kwargs, "slave": self._unit}), timeout=self._io_timeout_s
            )
        except TypeError:
            try:
                resp = await asyncio.wait_for(
                    func(**{**kwargs, "unit": self._unit}), timeout=self._io_timeout_s
                )
            except TypeError:
                resp = await asyncio.wait_for(
                    func(**kwargs), timeout=self._io_timeout_s
                )
        # Normalize error checking
        if isinstance(resp, ExceptionResponse) or (
            hasattr(resp, "isError") and resp.isError()
        ):
            raise ModbusException(f"Modbus error on {method} with {kwargs}")
        return resp

    async def read_registers(
        self, address: int, count: int, input_type: str = "holding"
    ) -> list[int]:
        """Read registers from the device."""
        if input_type == "input":
            rr = await self._call("read_input_registers", address=address, count=count)
        else:
            rr = await self._call(
                "read_holding_registers", address=address, count=count
            )

        regs = getattr(rr, "registers", None)
        if regs is None:
            raise ModbusException("No registers returned")
        return list(regs)

    @staticmethod
    def decode_registers(regs: list[int], data_type: str | None) -> float | int:
        """Decode registers to a value."""
        # All decoding assumes big-endian word and byte order.
        if data_type == "float32":
            raw = struct.pack(">HH", int(regs[0]) & 0xFFFF, int(regs[1]) & 0xFFFF)
            return float(struct.unpack(">f", raw)[0])
        if data_type == "int16":
            v = int(regs[0]) & 0xFFFF
            return v - 0x10000 if v & 0x8000 else v
        if data_type == "uint16":
            return int(regs[0]) & 0xFFFF
        if data_type == "uint32":
            return ((int(regs[0]) & 0xFFFF) << 16) | (int(regs[1]) & 0xFFFF)
        if data_type == "int32":
            u = ((int(regs[0]) & 0xFFFF) << 16) | (int(regs[1]) & 0xFFFF)
            return u - 0x1_0000_0000 if u & 0x8000_0000 else u
        # Fallback to first register as unsigned 16-bit
        return int(regs[0]) & 0xFFFF

    async def resolve_ip(self) -> str | None:
        """Resolve the host to an IP address."""
        with contextlib.suppress(ValueError):
            return str(ipaddress.ip_address(self._host))

        try:
            infos = await asyncio.get_running_loop().getaddrinfo(
                self._host,
                None,
                type=socket.SOCK_STREAM,
            )
        except OSError:
            return None

        for family, _, _, _, sockaddr in infos:
            if not sockaddr:
                continue
            addr = sockaddr[0]
            if not isinstance(addr, str):
                continue
            if family == socket.AF_INET6 and addr.startswith("::ffff:"):
                addr = addr.removeprefix("::ffff:")
            return addr

        return None
