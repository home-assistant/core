"""Hub wrapper for the Elke27 client lifecycle."""

from __future__ import annotations

from typing import Any, Callable

from elke27_lib.client import Elke27Client, Result

from .const import READY_TIMEOUT


class Elke27Hub:
    """Manage a single Elke27 client instance and its snapshots."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the hub wrapper."""
        self._client = Elke27Client(host, port)
        self._unsubscribe: Callable[[], None] | None = None
        self._last_result: Result | None = None
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

    async def async_start(self) -> None:
        """Connect and start the client, then await readiness."""
        await self._client.start()
        if not self._client.is_ready:
            await self._client.wait_ready(timeout_s=READY_TIMEOUT)
        if not self._client.is_ready:
            raise TimeoutError("Client did not become ready before timeout")
        self._unsubscribe = self._client.subscribe(self._handle_event)
        self._refresh_snapshots()

    async def async_stop(self) -> None:
        """Stop the client and unregister event handlers."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await self._client.stop()

    def _handle_event(self, result: Result) -> None:
        """Handle semantic events from the client."""
        self._last_result = result
        self._refresh_snapshots()

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
