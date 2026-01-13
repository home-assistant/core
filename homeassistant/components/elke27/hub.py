"""Hub wrapper for the Elke27 client lifecycle."""

from __future__ import annotations

import contextlib
import asyncio
from enum import Enum
import inspect
import logging
from typing import Any, Callable

from elke27_lib import ArmMode, ClientConfig, Elke27Client, LinkKeys
from elke27_lib.errors import Elke27LinkRequiredError, Elke27PinRequiredError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError

from .const import READY_TIMEOUT
from .identity import build_client_identity

_LOGGER = logging.getLogger(__name__)

_SYSTEM_EVENT_TYPES = {"SYSTEM", "PANEL", "PANEL_INFO", "TABLE_INFO"}


class Elke27Hub:
    """Manage a single Elke27 client instance and its snapshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        link_keys_json: str,
        integration_serial: str,
        pin: str | None,
        panel_name: str | None,
    ) -> None:
        """Initialize the hub wrapper."""
        self._hass = hass
        self._host = host
        self._port = port
        self._link_keys_json = link_keys_json
        self._integration_serial = integration_serial
        self._pin = pin
        self._panel_name = panel_name
        self._client: Elke27Client | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._listeners: list[Callable[[], None]] = []
        self._area_listeners: list[Callable[[], None]] = []
        self._zone_listeners: list[Callable[[], None]] = []
        self._output_listeners: list[Callable[[], None]] = []
        self._system_listeners: list[Callable[[], None]] = []
        self.snapshot: Any | None = None
        self._connect_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempts = 0
        self._stopping = False
        self._unavailable_logged = False

    @property
    def client(self) -> Elke27Client | None:
        """Return the underlying client."""
        return self._client

    @property
    def is_ready(self) -> bool:
        """Return if the client is ready."""
        if self._client is None:
            return False
        return bool(getattr(self._client, "is_ready", False))

    @property
    def panel_info(self) -> Any | None:
        """Return the latest panel info snapshot."""
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return getattr(snapshot, "panel_info", None) or getattr(snapshot, "panel", None)

    @property
    def panel_name(self) -> str | None:
        """Return the discovered panel name if available."""
        return self._panel_name

    @property
    def table_info(self) -> Any | None:
        """Return the latest table info snapshot."""
        snapshot = self.snapshot
        return getattr(snapshot, "table_info", None) if snapshot is not None else None

    @property
    def areas(self) -> Any | None:
        """Return the latest areas snapshot."""
        snapshot = self.snapshot
        return getattr(snapshot, "areas", None) if snapshot is not None else None

    @property
    def zones(self) -> Any | None:
        """Return the latest zones snapshot."""
        snapshot = self.snapshot
        return getattr(snapshot, "zones", None) if snapshot is not None else None

    @property
    def outputs(self) -> Any | None:
        """Return the latest outputs snapshot."""
        snapshot = self.snapshot
        return getattr(snapshot, "outputs", None) if snapshot is not None else None

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for any hub updates."""
        return self._add_listener(self._listeners, listener)

    @callback
    def async_add_area_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for area updates."""
        return self._add_listener(self._area_listeners, listener)

    @callback
    def async_add_zone_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for zone updates."""
        return self._add_listener(self._zone_listeners, listener)

    @callback
    def async_add_output_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for output updates."""
        return self._add_listener(self._output_listeners, listener)

    @callback
    def async_add_system_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for system updates."""
        return self._add_listener(self._system_listeners, listener)

    async def async_start(self) -> None:
        """Connect the client, then await readiness."""
        self._stopping = False
        await self._async_connect()

    async def _async_connect(self) -> None:
        """Connect the client, then await readiness."""
        async with self._connect_lock:
            await self._async_disconnect()
            link_keys = LinkKeys.from_json(self._link_keys_json)
            client = Elke27Client(ClientConfig())
            client_identity = build_client_identity(self._integration_serial)
            # Elke27Client v2 does not expose a public identity setter yet.
            coerce_identity = getattr(client, "_coerce_identity", None)
            if callable(coerce_identity):
                client._v2_client_identity = coerce_identity(client_identity)
            self._client = client
            try:
                await client.async_connect(self._host, self._port, link_keys)
                if self._panel_name is None:
                    panel_name = await self._async_discover_panel_name(client)
                    if panel_name:
                        self._panel_name = panel_name
                        _LOGGER.debug("Discovered panel name: %s", panel_name)
                if self._pin:
                    auth_result = await client.async_execute(
                        "control_authenticate", pin=int(self._pin)
                    )
                    if not getattr(auth_result, "ok", False):
                        error = getattr(auth_result, "error", None)
                        message = str(error) if error is not None else "Invalid PIN"
                        raise ConfigEntryAuthFailed(message)
                ready = await client.wait_ready(timeout_s=READY_TIMEOUT)
                if not ready:
                    raise ConfigEntryNotReady(
                        "The client did not become ready before timeout"
                    )
                self._unsubscribe = client.subscribe(self._handle_event)
                self.snapshot = client.snapshot
                if self._unavailable_logged:
                    _LOGGER.info("Panel connection restored")
                    self._unavailable_logged = False
            except Exception:
                with contextlib.suppress(Exception):
                    await client.async_disconnect()
                self._client = None
                raise

    async def async_stop(self) -> None:
        """Disconnect the client and unregister event handlers."""
        self._stopping = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None
        await self._async_disconnect()

    async def _async_disconnect(self) -> None:
        """Disconnect the client and unregister event handlers."""
        was_connected = self._client is not None or self.snapshot is not None
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._client is not None:
            await self._client.async_disconnect()
        self._client = None
        self.snapshot = None
        if was_connected:
            self._log_unavailable()

    async def _async_discover_panel_name(self, client: Elke27Client) -> str | None:
        """Return the panel name from discovery if available."""
        panels = await client.async_discover(timeout_s=5, address=self._host)
        if not panels:
            return None
        panel = panels[0]
        return getattr(panel, "panel_name", None)

    async def async_set_output(self, output_id: int, state: bool) -> bool:
        """Request an output state change if supported."""
        client = self._client
        if client is None:
            return False

        method = getattr(client, "async_set_output", None)
        if method is None:
            method = getattr(client, "set_output", None)
        if method is None:
            _LOGGER.warning(
                "Output control is not supported by the client for output %s",
                output_id,
            )
            return False
        params = inspect.signature(method).parameters
        if "on" in params:
            args = (output_id,)
            kwargs = {"on": state}
        else:
            args = (output_id, state)
            kwargs = {}
        if inspect.iscoroutinefunction(method):
            result = await method(*args, **kwargs)
        else:
            result = await self._hass.async_add_executor_job(method, *args, **kwargs)
        return bool(result) if isinstance(result, bool) else True

    async def async_set_zone_bypass(self, zone_id: int, bypassed: bool) -> bool:
        """Request a zone bypass change."""
        client = self._client
        if client is None:
            return False
        pin = self._pin
        if not pin:
            raise Elke27PinRequiredError("PIN required to bypass zones.")
        pin_value = int(pin)
        _LOGGER.debug(
            "Sending zone bypass request: zone_id=%s bypassed=%s pin=%s",
            zone_id,
            bypassed,
            pin_value,
        )
        timeout_s = 15.0
        start = self._hass.loop.time()
        result = await client.async_execute(
            "zone_set_status",
            zone_id=zone_id,
            pin=pin_value,
            bypassed=bypassed,
            timeout_s=timeout_s,
        )
        elapsed = self._hass.loop.time() - start
        _LOGGER.debug(
            "Zone bypass reply for zone %s in %.2fs (timeout %.1fs)",
            zone_id,
            elapsed,
            timeout_s,
        )
        if not getattr(result, "ok", False):
            error = getattr(result, "error", None)
            if error is not None:
                raise error
            return False
        status_result = await client.async_execute(
            "zone_get_status",
            zone_id=zone_id,
        )
        if not getattr(status_result, "ok", False):
            _LOGGER.debug(
                "Zone status refresh failed for zone %s: %s",
                zone_id,
                getattr(status_result, "error", None),
            )
        return True

    async def async_arm_area(
        self, area_id: int, mode: Any, pin: str | None
    ) -> bool:
        """Request an area arming change if supported."""
        client = self._client
        if client is None:
            return False
        if pin is None:
            raise Elke27PinRequiredError("PIN required to arm areas.")
        try:
            pin_value = int(pin)
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("Code must be numeric.") from err

        if mode is ArmMode.ARMED_STAY:
            arm_state = "ARMED_STAY"
        elif mode is ArmMode.ARMED_AWAY:
            arm_state = "ARMED_AWAY"
        else:
            raise HomeAssistantError("Arm mode is not supported.")
        result = await client.async_execute(
            "area_set_arm_state",
            area_id=area_id,
            arm_state=arm_state,
            pin=pin_value,
        )
        if not getattr(result, "ok", False):
            error = getattr(result, "error", None)
            error_message = getattr(error, "user_message", None) or getattr(
                error, "message", None
            )
            _LOGGER.warning(
                "Area arming failed for area %s: %s",
                area_id,
                error_message or error,
            )
            if error is not None:
                raise HomeAssistantError(
                    error_message or str(error)
                ) from error
            return False
        return True

    async def async_disarm_area(self, area_id: int, pin: str | None) -> bool:
        """Request an area disarming change if supported."""
        client = self._client
        if client is None:
            return False
        if pin is None:
            raise Elke27PinRequiredError("PIN required to disarm areas.")
        try:
            pin_value = int(pin)
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("Code must be numeric.") from err

        result = await client.async_execute(
            "area_set_arm_state",
            area_id=area_id,
            arm_state="DISARMED",
            pin=pin_value,
        )
        if not getattr(result, "ok", False):
            error = getattr(result, "error", None)
            error_message = getattr(error, "user_message", None) or getattr(
                error, "message", None
            )
            _LOGGER.warning(
                "Area disarm failed for area %s: %s",
                area_id,
                error_message or error,
            )
            if error is not None:
                raise HomeAssistantError(
                    error_message or str(error)
                ) from error
            return False
        return True

    def _handle_event(self, event: Any) -> None:
        """Handle events from the client."""
        if self._client is None:
            return
        self.snapshot = self._client.snapshot
        connection_state = _connection_state(event)
        event_type = _event_type(event)
        if connection_state is False or event_type == "DISCONNECTED":
            _LOGGER.debug("Panel disconnect event received; scheduling reconnect")
            self._log_unavailable()
            self._hass.loop.call_soon_threadsafe(self._schedule_reconnect)
        elif connection_state is True or event_type == "READY":
            self._hass.loop.call_soon_threadsafe(self._cancel_reconnect)
        if event_type == "ZONE":
            zone_id = _event_zone_id(event)
            if zone_id is not None:
                zone = _zone_from_snapshot(self.snapshot, zone_id)
                _LOGGER.debug(
                    "Zone %s snapshot bypassed=%s",
                    zone_id,
                    getattr(zone, "bypassed", None) if zone is not None else None,
                )
        self._dispatch(self._listeners)
        if event_type == "AREA":
            self._dispatch(self._area_listeners)
        elif event_type == "ZONE":
            self._dispatch(self._zone_listeners)
        elif event_type == "OUTPUT":
            self._dispatch(self._output_listeners)
        elif event_type in _SYSTEM_EVENT_TYPES:
            self._dispatch(self._system_listeners)

    @callback
    def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempts when the panel disconnects."""
        if self._stopping:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        _LOGGER.debug("Creating reconnect task")
        self._reconnect_task = self._hass.async_create_task(
            self._async_reconnect_loop()
        )

    @callback
    def _cancel_reconnect(self) -> None:
        """Cancel any scheduled reconnection attempts."""
        if self._reconnect_task is None:
            return
        if not self._reconnect_task.done():
            self._reconnect_task.cancel()
        self._reconnect_task = None
        self._reconnect_attempts = 0

    def _log_unavailable(self) -> None:
        """Log the panel as unavailable once."""
        if self._unavailable_logged:
            return
        _LOGGER.info("Panel connection lost")
        self._unavailable_logged = True

    async def _async_reconnect_loop(self) -> None:
        """Reconnect with exponential backoff until successful or stopped."""
        while not self._stopping:
            _LOGGER.debug("Reconnect attempt %s starting", self._reconnect_attempts + 1)
            try:
                await self._async_connect()
                self._reconnect_attempts = 0
                return
            except (ConfigEntryAuthFailed, Elke27LinkRequiredError) as err:
                _LOGGER.error("Reconnect aborted: %s", err)
                return
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Reconnect attempt failed: %s", err)
            self._reconnect_attempts += 1
            delay = min(300, 2 ** self._reconnect_attempts)
            _LOGGER.debug("Reconnect attempt %s sleeping for %s seconds", self._reconnect_attempts, delay)
            await asyncio.sleep(delay)

    @callback
    def _dispatch(self, listeners: list[Callable[[], None]]) -> None:
        """Schedule listener callbacks without blocking."""
        for listener in list(listeners):
            self._hass.loop.call_soon_threadsafe(listener)

    @callback
    def _add_listener(
        self, listeners: list[Callable[[], None]], listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Add a listener and return its unsubscribe callback."""
        listeners.append(listener)

        def _remove() -> None:
            if listener in listeners:
                listeners.remove(listener)

        return _remove


def _event_type(event: Any) -> str | None:
    if isinstance(event, dict):
        value = event.get("type") or event.get("event_type") or event.get("domain")
        if isinstance(value, Enum):
            return str(value.value).upper()
        return str(value).upper() if value else None
    for attr in ("type", "event_type", "domain", "kind", "category"):
        value = getattr(event, attr, None)
        if value:
            if isinstance(value, Enum):
                return str(value.value).upper()
            return str(value).upper()
    return None


def _connection_state(event: Any) -> bool | None:
    if hasattr(event, "event_type"):
        event_type = getattr(event, "event_type")
        value = event_type.value if isinstance(event_type, Enum) else str(event_type).lower()
        if value == "connection":
            data = getattr(event, "data", None)
            if isinstance(data, dict):
                connected = data.get("connected")
                if isinstance(connected, bool):
                    return connected
        if value == "disconnected":
            return False
        if value == "ready":
            return True
        return None
    connected = getattr(event, "connected", None)
    return connected if isinstance(connected, bool) else None


def _event_zone_id(event: Any) -> int | None:
    if isinstance(event, dict):
        for key in ("zone_id", "id"):
            value = event.get(key)
            if isinstance(value, int):
                return value
        return None
    return getattr(event, "zone_id", None)


def _zone_from_snapshot(snapshot: Any, zone_id: int) -> Any | None:
    if snapshot is None:
        return None
    zones = getattr(snapshot, "zones", None)
    if isinstance(zones, dict):
        return zones.get(zone_id)
    if isinstance(zones, list | tuple):
        for zone in zones:
            if getattr(zone, "zone_id", None) == zone_id:
                return zone
    return None
