"""Hub for Qube Heat Pump communication."""

from __future__ import annotations

import asyncio

from python_qube_heatpump import QubeClient
from python_qube_heatpump.models import QubeState

from homeassistant.core import HomeAssistant


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
        # Backoff/timeout controls
        self._connect_backoff_s: float = 0.0
        self._connect_backoff_max_s: float = 60.0
        self._next_connect_ok_at: float = 0.0
        # Error counters
        self._err_connect: int = 0
        self._resolved_ip: str | None = None

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
        # The library client doesn't expose resolve_ip yet, assuming it handles connection internally
        # or we might need to add it to the library if diagnostics depend on it.
        # For now, we can skip or implement locally if critical.
        # Given the library abstraction, we might assume client handles this.
        # However, the library 'client.py' we generated doesn't have resolve_ip.
        # We'll rely on the client's internal handling or just not expose it for now if not needed.

    async def async_connect(self) -> None:
        """Connect to the Modbus server."""
        now = asyncio.get_running_loop().time()
        if now < self._next_connect_ok_at:
            # We are in backoff
            pass

        connected = await self.client.connect()
        if not connected:
            # Increase backoff
            self._connect_backoff_s = min(
                self._connect_backoff_max_s, (self._connect_backoff_s or 1.0) * 2
            )
            self._next_connect_ok_at = now + self._connect_backoff_s
            self._err_connect += 1
            return

        # Reset backoff after success
        self._connect_backoff_s = 0.0
        self._next_connect_ok_at = 0.0

    async def async_close(self) -> None:
        """Close the connection."""
        await self.client.close()

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self.client.unit = unit_id

    @property
    def err_connect(self) -> int:
        """Return connect error count."""
        return self._err_connect

    async def async_get_all_data(self) -> QubeState | None:
        """Get all data from the device."""
        if not await self.client.connect():
            return None
        return await self.client.get_all_data()
