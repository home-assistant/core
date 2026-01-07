"""Hub for Qube Heat Pump communication."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import ipaddress
import logging
import socket
import struct
from typing import TYPE_CHECKING, Any, cast

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in str(text)).strip("_").lower()


@dataclass
class EntityDef:
    """Definition of a Qube entity."""

    platform: str
    name: str | None
    address: int
    vendor_id: str | None = None
    input_type: str | None = None
    write_type: str | None = None
    data_type: str | None = None
    unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    precision: int | None = None
    unique_id: str | None = None
    offset: float | None = None
    scale: float | None = None
    min_value: float | None = None
    translation_key: str | None = None


class QubeHub:
    """Qube Heat Pump Hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        entry_id: str,
        unit_id: int = 1,
        label: str | None = None,
    ) -> None:
        """Initialize the hub."""
        self._hass = hass
        self._host = host
        self._port = port
        self.entry_id = entry_id
        self._unit = unit_id
        self._label = label or "qube1"
        self._client: AsyncModbusTcpClient | None = None
        self.entities: list[EntityDef] = []
        # Backoff/timeout controls
        self._connect_backoff_s: float = 0.0
        self._connect_backoff_max_s: float = 60.0
        self._next_connect_ok_at: float = 0.0
        self._io_timeout_s: float = 3.0
        # Error counters
        self._err_connect: int = 0
        self._err_read: int = 0
        self._resolved_ip: str | None = None
        self._translations: dict[str, Any] = {}

    def set_translations(self, translations: dict[str, Any]) -> None:
        """Set translations for friendly name resolution."""
        self._translations = translations

    def get_friendly_name(self, platform: str, key: str | None) -> str | None:
        """Get friendly name from translations."""
        if not key or not self._translations:
            return None
        # Structure: entity -> platform -> key -> name
        with contextlib.suppress(Exception):
            val = (
                self._translations.get("entity", {})
                .get(platform, {})
                .get(key, {})
                .get("name")
            )
            return cast("str | None", val)
        return None

    @property
    def host(self) -> str:
        """Return host."""
        return self._host

    @property
    def unit(self) -> int:
        """Return unit ID."""
        return self._unit

    @property
    def label(self) -> str:
        """Return label."""
        return self._label

    @property
    def resolved_ip(self) -> str | None:
        """Return resolved IP address."""
        return self._resolved_ip

    async def async_resolve_ip(self) -> None:
        """Resolve the host to a concrete IP address for diagnostics."""
        with contextlib.suppress(ValueError):
            self._resolved_ip = str(ipaddress.ip_address(self._host))
            return

        try:
            infos = await asyncio.get_running_loop().getaddrinfo(
                self._host,
                None,
                type=socket.SOCK_STREAM,
            )
        except OSError:
            self._resolved_ip = None
            return

        for family, _, _, _, sockaddr in infos:
            if not sockaddr:
                continue
            addr = sockaddr[0]
            if not isinstance(addr, str):
                continue
            if family == socket.AF_INET6 and addr.startswith("::ffff:"):
                addr = addr.removeprefix("::ffff:")
            self._resolved_ip = addr
            return

        self._resolved_ip = None

    async def async_connect(self) -> None:
        """Connect to the Modbus server."""
        now = asyncio.get_running_loop().time()
        if now < self._next_connect_ok_at:
            raise ModbusException("Backoff active; skipping connect attempt")
        if self._client is None:
            self._client = AsyncModbusTcpClient(self._host, port=self._port)
        connected = bool(getattr(self._client, "connected", False))
        if not connected:
            try:
                ok = await asyncio.wait_for(
                    self._client.connect(), timeout=self._io_timeout_s
                )
            except Exception as exc:
                # Increase backoff
                self._connect_backoff_s = min(
                    self._connect_backoff_max_s, (self._connect_backoff_s or 1.0) * 2
                )
                self._next_connect_ok_at = now + self._connect_backoff_s
                self._err_connect += 1
                raise ModbusException(f"Failed to connect: {exc}") from exc
            if ok is False:
                self._connect_backoff_s = min(
                    self._connect_backoff_max_s, (self._connect_backoff_s or 1.0) * 2
                )
                self._next_connect_ok_at = now + self._connect_backoff_s
                self._err_connect += 1
                raise ModbusException("Failed to connect to Modbus TCP server")
            # Reset backoff after success
            self._connect_backoff_s = 0.0
            self._next_connect_ok_at = 0.0

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

    async def async_close(self) -> None:
        """Close the connection."""
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.close()
            self._client = None

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self._unit = int(unit_id)

    @property
    def err_connect(self) -> int:
        """Return connect error count."""
        return self._err_connect

    @property
    def err_read(self) -> int:
        """Return read error count."""
        return self._err_read

    def inc_read_error(self) -> None:
        """Increment read error count."""
        self._err_read += 1

    async def async_read_value(self, ent: EntityDef) -> Any:
        """Read a value from the device."""
        if self._client is None:
            raise ModbusException("Client not connected")

        # sensor
        return await self._read_sensor(ent)

    async def _read_sensor(self, ent: EntityDef) -> Any:
        count = 1
        if ent.data_type in ("float32", "uint32", "int32"):
            count = 2

        try:
            if ent.input_type == "input":
                rr = await self._call(
                    "read_input_registers", address=ent.address, count=count
                )
            else:
                # default to holding
                rr = await self._call(
                    "read_holding_registers", address=ent.address, count=count
                )
        except ModbusException:
            # Some devices/YAMLs use 1-based addresses; try address-1 as fallback
            fallback_addr = ent.address - 1
            if fallback_addr < 0:
                raise
            logging.getLogger(__name__).info(
                "Modbus read failed @ %s, retrying @ %s (fallback)",
                ent.address,
                fallback_addr,
            )
            if ent.input_type == "input":
                rr = await self._call(
                    "read_input_registers", address=fallback_addr, count=count
                )
            else:
                rr = await self._call(
                    "read_holding_registers", address=fallback_addr, count=count
                )

        regs = getattr(rr, "registers", None)
        if regs is None:
            raise ModbusException("No registers returned")

        val = self._decode_registers(regs, ent.data_type)
        return self._apply_post_process(val, ent)

    def _decode_registers(self, regs: list[int], data_type: str | None) -> float | int:
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

    def _apply_post_process(self, val: float, ent: EntityDef) -> float:
        # Apply scale/offset as value = value * scale + offset
        if ent.scale is not None:
            with contextlib.suppress(ValueError, TypeError):
                val = float(val) * float(ent.scale)
        if ent.offset is not None:
            with contextlib.suppress(ValueError, TypeError):
                val = float(val) + float(ent.offset)

        # Clamp to minimum value if configured
        if ent.min_value is not None:
            with contextlib.suppress(ValueError, TypeError):
                if float(val) < float(ent.min_value):
                    val = float(ent.min_value)

        if ent.precision is not None:
            with contextlib.suppress(ValueError, TypeError):
                p = int(ent.precision)
                f = float(val)
                val = round(f) if p == 0 else round(f, p)
        return val

    async def async_write_register(
        self, address: int, value: float, data_type: str = "uint16"
    ) -> None:
        """Write a value to a register."""
        if self._client is None:
            raise ModbusException("Client not connected")

        data_type = (data_type or "uint16").lower()

        async def _write(addr: int) -> None:
            if data_type in ("float32", "float"):
                raw = struct.pack(">f", float(value))
                hi = int.from_bytes(raw[:2], "big")
                lo = int.from_bytes(raw[2:], "big")
                await self._call(
                    "write_registers", address=addr, values=[hi & 0xFFFF, lo & 0xFFFF]
                )
                return

            if data_type in ("int16", "int"):
                int_val = round(float(value))
                if not -32768 <= int_val <= 32767:
                    raise ModbusException("int16 value out of range")
                if int_val < 0:
                    int_val = (1 << 16) + int_val
                await self._call("write_register", address=addr, value=int_val & 0xFFFF)
                return

            if data_type in ("uint16", "uint"):
                int_val = round(float(value))
                if not 0 <= int_val <= 0xFFFF:
                    raise ModbusException("uint16 value out of range")
                await self._call("write_register", address=addr, value=int_val & 0xFFFF)
                return

            raise ModbusException(
                f"Unsupported data_type for register write: {data_type}"
            )

        try:
            await _write(address)
        except ModbusException:
            fallback_addr = address - 1
            if fallback_addr < 0:
                raise
            logging.getLogger(__name__).info(
                "Modbus register write failed @ %s, retrying @ %s (fallback)",
                address,
                fallback_addr,
            )
            await _write(fallback_addr)
