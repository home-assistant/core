"""Hub wrapper for the Elke27 client lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
import inspect
import logging
from typing import Any, Callable

from elke27_lib.client import E27Identity, E27LinkKeys, Elke27Client, Result

from homeassistant.core import callback

from .const import MANUFACTURER_NUMBER, READY_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class Elke27Hub:
    """Manage a single Elke27 client instance and its snapshots."""

    def __init__(
        self,
        host: str,
        port: int,
        link_keys: Any,
        panel: Any | None,
        integration_serial: str,
    ) -> None:
        """Initialize the hub wrapper."""
        self._client = Elke27Client()
        self._host = host
        self._port = port
        self._link_keys = link_keys
        self._panel = panel
        self._integration_serial = integration_serial
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

    @callback
    def async_add_output_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for output updates."""
        return self.async_add_listener(listener)

    async def async_start(self) -> None:
        """Connect the client, then await readiness."""
        panel = self._panel or {"panel_host": self._host, "port": self._port}
        link_keys = _link_keys_from_data(self._link_keys)
        client_identity = _client_identity(self._integration_serial)
        result = await self._client.connect(
            link_keys,
            panel=panel,
            client_identity=client_identity,
        )
        if not result.ok:
            if isinstance(result.error, Exception):
                raise result.error
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

    async def async_set_output(self, output_id: int, state: bool) -> bool:
        """Request an output state change if supported."""
        method = None
        if hasattr(self._client, "set_output"):
            method = self._client.set_output
        elif hasattr(self._client, "set_output_state"):
            method = self._client.set_output_state

        if method is None:
            _LOGGER.warning(
                "Output control is not supported by the client for output %s",
                output_id,
            )
            return False

        if inspect.iscoroutinefunction(method):
            result = await method(output_id, state)
        else:
            result = await asyncio.to_thread(method, output_id, state)

        if isinstance(result, Result):
            if not result.ok:
                _LOGGER.warning(
                    "Output %s state change failed: %s",
                    output_id,
                    result.error or "unknown error",
                )
                return False
            return True
        if isinstance(result, bool):
            return result
        return True

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


def _client_identity(integration_serial: str) -> E27Identity:
    """Build the client identity for connect."""
    return E27Identity(
        mn=str(MANUFACTURER_NUMBER),
        sn=integration_serial,
        fwver="0",
        hwver="0",
        osver="0",
    )


def _link_keys_from_data(data: Any) -> E27LinkKeys:
    """Normalize link keys from stored entry data."""
    if isinstance(data, E27LinkKeys):
        return data
    if is_dataclass(data):
        data = asdict(data)
    if isinstance(data, dict):
        tempkey = data.get("tempkey_hex") or data.get("temp_key") or data.get("tempkey")
        linkkey = data.get("linkkey_hex") or data.get("link_key") or data.get("linkkey")
        linkhmac = data.get("linkhmac_hex") or data.get("link_hmac") or data.get("linkhmac")
        if tempkey and linkkey and linkhmac:
            return E27LinkKeys(
                tempkey_hex=str(tempkey),
                linkkey_hex=str(linkkey),
                linkhmac_hex=str(linkhmac),
            )
    raise ValueError("Link keys are missing required fields")
