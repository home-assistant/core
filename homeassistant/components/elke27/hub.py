"""Hub wrapper for the Elke27 client lifecycle."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from elke27_lib.client import Elke27Client, Result

from homeassistant.core import callback

from .const import READY_TIMEOUT


class Elke27Hub:
    """Manage a single Elke27 client instance and its snapshots."""

    def __init__(self, host: str, port: int, link_keys: Any, panel: Any | None) -> None:
        """Initialize the hub wrapper."""
        self._client = Elke27Client(host, port)
        self._link_keys = link_keys
        self._panel = panel
        self._last_result: Result | None = None
        self._listeners: list[Callable[[], None]] = []
        self.panel_info: Any | None = None
        self.table_info: Any | None = None
        self.areas: Any | None = None
        self.zones: Any | None = None
        self.keypads: Any | None = None
        self.outputs: Any | None = None
        self.counters: Any | None = None
        self.settings: Any | None = None
        self.tasks: Any | None = None
        self.thermostats: Any | None = None

    @property
    def client(self) -> Elke27Client:
        """Return the underlying client."""
        return self._client

    @property
    def is_ready(self) -> bool:
        """Return if the client is ready."""
        return self._client.is_ready

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for hub updates."""
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    @callback
    def async_add_area_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for area updates."""
        return self.async_add_listener(listener)

    @callback
    def async_add_zone_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for zone updates."""
        return self.async_add_listener(listener)

    async def async_start(self) -> None:
        """Connect the client, then await readiness."""
        result = await self._client.connect(self._link_keys, panel=self._panel)
        if not result.ok:
            raise RuntimeError(result.error or "Connect failed")

        if not self._client.is_ready:
            ready = await asyncio.to_thread(
                self._client.wait_ready, timeout_s=READY_TIMEOUT
            )
            if not ready:
                raise TimeoutError("Client did not become ready before timeout")
        if not self._client.is_ready:
            raise TimeoutError("Client did not become ready before timeout")
        self._client.subscribe(self._handle_event)
        self._refresh_snapshots()

    async def async_stop(self) -> None:
        """Disconnect the client and unregister event handlers."""
        self._client.unsubscribe(self._handle_event)
        await self._client.disconnect()

    def _handle_event(self, result: Result) -> None:
        """Handle semantic events from the client."""
        self._last_result = result
        self._refresh_snapshots()
        for listener in list(self._listeners):
            listener()

    def _refresh_snapshots(self) -> None:
        """Capture the latest snapshots from the client."""
        self.panel_info = getattr(self._client, "panel_info", None)
        self.table_info = getattr(self._client, "table_info", None)
        self.areas = getattr(self._client, "areas", None)
        self.zones = getattr(self._client, "zones", None)
        self.keypads = getattr(self._client, "keypads", None)
        self.outputs = getattr(self._client, "outputs", None)
        self.counters = getattr(self._client, "counters", None)
        self.settings = getattr(self._client, "settings", None)
        self.tasks = getattr(self._client, "tasks", None)
        self.thermostats = getattr(self._client, "thermostats", None)
