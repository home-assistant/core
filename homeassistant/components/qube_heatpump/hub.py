"""Hub for Qube Heat Pump communication."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, cast

from python_qube_heatpump import QubeClient

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


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
        self.entry_id = entry_id
        self._label = label or "qube1"
        self.client = QubeClient(host, port, unit_id)
        self.entities: list[EntityDef] = []
        # Backoff/timeout controls
        self._connect_backoff_s: float = 0.0
        self._connect_backoff_max_s: float = 60.0
        self._next_connect_ok_at: float = 0.0
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
        return self.client.host

    @property
    def unit(self) -> int:
        """Return unit ID."""
        return self.client.unit

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
        self._resolved_ip = await self.client.resolve_ip()

    async def async_connect(self) -> None:
        """Connect to the Modbus server."""
        now = asyncio.get_running_loop().time()
        if now < self._next_connect_ok_at:
            # We are in backoff
            # Only raise if we really need to downstream, but typically
            # we just want to ensure we don't spam connect
            pass

        connected = await self.client.connect()
        if not connected:
            # Increase backoff
            self._connect_backoff_s = min(
                self._connect_backoff_max_s, (self._connect_backoff_s or 1.0) * 2
            )
            self._next_connect_ok_at = now + self._connect_backoff_s
            self._err_connect += 1
            # We don't raise here to avoid crashing setup/update cycles excessively,
            # allowing retry later. But if caller expects connection, they check is_connected.
            return

        # Reset backoff after success
        self._connect_backoff_s = 0.0
        self._next_connect_ok_at = 0.0

    async def async_close(self) -> None:
        """Close the connection."""
        await self.client.close()

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self.client.set_unit_id(unit_id)

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
        if not self.client.is_connected:
            await self.async_connect()
            if not self.client.is_connected:
                raise HomeAssistantError("Client not connected")

        count = 1
        if ent.data_type in ("float32", "uint32", "int32"):
            count = 2

        try:
            regs = await self.client.read_registers(
                ent.address, count, ent.input_type or "holding"
            )
        except Exception:
            # Try fallback address - 1
            fallback_addr = ent.address - 1
            if fallback_addr < 0:
                raise
            logging.getLogger(__name__).info(
                "Modbus read failed @ %s, retrying @ %s (fallback)",
                ent.address,
                fallback_addr,
            )
            regs = await self.client.read_registers(
                fallback_addr, count, ent.input_type or "holding"
            )

        val = self.client.decode_registers(regs, ent.data_type)
        return self._apply_post_process(val, ent)

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
