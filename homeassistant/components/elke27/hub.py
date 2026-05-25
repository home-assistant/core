"""Hub wrapper for the Elke27 client lifecycle."""

import asyncio
from collections.abc import Callable
import contextlib
from enum import Enum
import logging
from typing import Any

from elke27_lib import ArmMode, ClientConfig, LinkKeys
from elke27_lib.client import Elke27Client
from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27Error,
    Elke27InvalidArgument,
    Elke27LinkRequiredError,
    Elke27PinRequiredError,
    Elke27TimeoutError,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .const import READY_TIMEOUT
from .identity import build_client_identity

_LOGGER = logging.getLogger(__name__)


def _raise_command_error(action: str, error: BaseException) -> None:
    """Raise a Home Assistant error for a failed client command."""
    message = (
        getattr(error, "user_message", None)
        or getattr(error, "message", None)
        or str(error)
        or f"{action} failed."
    )
    raise HomeAssistantError(message) from error


class Elke27Hub:
    """Manage a single Elke27 client instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        link_keys_json: str,
        client_id: str,
        panel_name: str | None,
    ) -> None:
        """Initialize the hub wrapper."""
        self._hass = hass
        self._host = host
        self._port = port
        self._link_keys_json = link_keys_json
        self._client_id = client_id
        self._panel_name = panel_name
        self._client: Elke27Client | None = None
        self._connection_unsubscribe: Callable[[], None] | None = None
        self._connect_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempts = 0
        self._stopping = False
        self._unavailable_logged = False
        self._typed_callbacks: dict[
            Callable[[Any], None], Callable[[], None] | None
        ] = {}

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
    def panel_name(self) -> str | None:
        """Return the configured panel name if available."""
        return self._panel_name

    async def async_connect(self) -> None:
        """Connect the client, then await readiness."""
        self._stopping = False
        await self._async_connect()

    async def _async_connect(self) -> None:
        """Connect the client, then await readiness."""
        async with self._connect_lock:
            await self._async_disconnect(log_unavailable=False)
            link_keys = LinkKeys.from_json(self._link_keys_json)
            client = Elke27Client(ClientConfig())
            client_identity = build_client_identity(self._client_id)
            _set_client_identity(client, client_identity)
            self._client = client

            def _raise_not_ready() -> None:
                msg = "The client did not become ready before timeout"
                raise ConfigEntryNotReady(msg)

            try:
                await client.async_connect(
                    host=self._host, port=self._port, link_keys=link_keys
                )
                ready = await client.wait_ready(timeout_s=READY_TIMEOUT)
                if not ready:
                    _raise_not_ready()
                self._connection_unsubscribe = client.subscribe(
                    self._handle_connection_event
                )
                self._resubscribe_typed_callbacks()
                if self._unavailable_logged:
                    _LOGGER.info("Panel connection restored")
                    self._unavailable_logged = False
            except Exception:
                with contextlib.suppress(Exception):
                    await client.async_disconnect()
                self._client = None
                raise

    async def async_disconnect(self) -> None:
        """Disconnect the client and unregister event handlers."""
        self._stopping = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None
        await self._async_disconnect()

    async def _async_disconnect(self, *, log_unavailable: bool = True) -> None:
        """Disconnect the client and unregister event handlers."""
        was_connected = self._client is not None
        if self._connection_unsubscribe is not None:
            with contextlib.suppress(Exception):
                self._connection_unsubscribe()
            self._connection_unsubscribe = None
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.async_disconnect()
        self._client = None
        self._clear_typed_subscriptions()
        if was_connected and not self._stopping and log_unavailable:
            self._log_unavailable()

    def get_snapshot(self) -> Any | None:
        """Return the latest client snapshot."""
        client = self._client
        if client is None:
            return None
        return client.get_snapshot()

    async def refresh_csm(self) -> Any:
        """Refresh the panel CSM snapshot."""
        client = self._client
        if client is None:
            msg = "Client is not connected."
            raise HomeAssistantError(msg)
        return await client.async_refresh_csm()

    async def refresh_domain_config(self, domain: str) -> None:
        """Refresh a domain configuration snapshot."""
        client = self._client
        if client is None:
            msg = "Client is not connected."
            raise HomeAssistantError(msg)
        await client.async_refresh_domain_config(domain)

    def subscribe(self, listener: Callable[[Any], None]) -> Callable[[], None]:
        """Subscribe to client events."""
        client = self._client
        if client is None:
            msg = "Client is not connected."
            raise HomeAssistantError(msg)
        return client.subscribe(listener)

    def subscribe_typed(self, listener: Callable[[Any], None]) -> Callable[[], None]:
        """Subscribe to typed client events."""
        if listener not in self._typed_callbacks:
            self._typed_callbacks[listener] = None
        client = self._client
        if client is not None and self._typed_callbacks[listener] is None:
            self._typed_callbacks[listener] = client.subscribe_typed(listener)

        def _remove() -> None:
            self.unsubscribe_typed(listener)

        return _remove

    def unsubscribe_typed(self, listener: Callable[[Any], None]) -> bool:
        """Unsubscribe from typed client events."""
        if listener in self._typed_callbacks:
            unsubscribe = self._typed_callbacks.pop(listener)
            if unsubscribe is not None:
                unsubscribe()
            return True
        client = self._client
        if client is None:
            return False
        return client.unsubscribe_typed(listener)

    async def async_set_zone_bypass(
        self, zone_id: int, *, bypassed: bool, pin: str | None = None
    ) -> bool:
        """Request a zone bypass change."""
        client = self._client
        if client is None:
            return False
        if pin is None:
            msg = "PIN required to bypass zones."
            raise Elke27PinRequiredError(msg)
        _LOGGER.debug(
            "Sending zone bypass request: zone_id=%s bypassed=%s",
            zone_id,
            bypassed,
        )
        try:
            await client.async_set_zone_bypass(zone_id, bypassed=bypassed, pin=pin)
        except Elke27PinRequiredError:
            raise
        except (Elke27Error, Elke27InvalidArgument, ValueError) as err:
            _raise_command_error("Zone bypass", err)
        return True

    async def async_arm_area(
        self,
        area_id: int,
        mode: Any,
        pin: str | None,
        *,
        auto_stay_cancel: bool = False,
        exit_delay_cancel: bool = False,
    ) -> bool:
        """Request an area arming change if supported."""
        client = self._client
        if client is None:
            return False
        if pin is None:
            msg = "PIN required to arm areas."
            raise Elke27PinRequiredError(msg)

        if mode is ArmMode.ARMED_STAY or (
            isinstance(mode, str) and mode.upper() == "ARMED_STAY"
        ):
            arm_mode = ArmMode.ARMED_STAY
        elif mode is ArmMode.ARMED_NIGHT or (
            isinstance(mode, str) and mode.upper() == "ARMED_NIGHT"
        ):
            arm_mode = ArmMode.ARMED_NIGHT
        elif (
            mode is ArmMode.ARMED_AWAY
            or (isinstance(mode, str) and mode.upper() == "ARMED_AWAY")
            or (isinstance(mode, str) and mode.upper() == "ARMED_CUSTOM_BYPASS")
        ):
            # The panel applies custom-bypass behavior by bypassing zones first,
            # then using the normal away arm command.
            arm_mode = ArmMode.ARMED_AWAY
        else:
            msg = "Arm mode is not supported."
            raise HomeAssistantError(msg)

        try:
            await client.async_arm_area(
                area_id,
                mode=arm_mode,
                pin=pin,
                auto_stay_cancel=auto_stay_cancel,
                exit_delay_cancel=exit_delay_cancel,
            )
        except Elke27PinRequiredError:
            raise
        except (Elke27Error, Elke27InvalidArgument, ValueError) as err:
            _raise_command_error("Area arming", err)
        return True

    def _resubscribe_typed_callbacks(self) -> None:
        """Re-register typed callbacks on a new client connection."""
        client = self._client
        if client is None or not self._typed_callbacks:
            return
        for cb in list(self._typed_callbacks):
            self._typed_callbacks[cb] = client.subscribe_typed(cb)

    def _clear_typed_subscriptions(self) -> None:
        """Clear typed subscriptions when the client disconnects."""
        for cb, unsubscribe in list(self._typed_callbacks.items()):
            if unsubscribe is not None:
                with contextlib.suppress(Exception):
                    unsubscribe()
            self._typed_callbacks[cb] = None

    async def async_disarm_area(
        self,
        area_id: int,
        pin: str | None,
        *,
        auto_stay_cancel: bool = False,
        exit_delay_cancel: bool = False,
    ) -> bool:
        """Request an area disarming change if supported."""
        client = self._client
        if client is None:
            return False
        if pin is None:
            msg = "PIN required to disarm areas."
            raise Elke27PinRequiredError(msg)

        try:
            await client.async_disarm_area(
                area_id,
                pin=pin,
                auto_stay_cancel=auto_stay_cancel,
                exit_delay_cancel=exit_delay_cancel,
            )
        except Elke27PinRequiredError:
            raise
        except (Elke27Error, Elke27InvalidArgument, ValueError) as err:
            _raise_command_error("Area disarm", err)
        return True

    def _handle_connection_event(self, event: Any) -> None:
        """Handle connection lifecycle events from the client."""
        if self._client is None:
            return
        connection_state = _connection_state(event)
        event_type = _event_type(event)
        if connection_state is False or event_type == "DISCONNECTED":
            _LOGGER.debug("Panel disconnect event received; scheduling reconnect")
            self._log_unavailable()
            self._hass.loop.call_soon_threadsafe(self._schedule_reconnect)
        elif connection_state is True or event_type == "READY":
            self._hass.loop.call_soon_threadsafe(self._cancel_reconnect)

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
            except Elke27LinkRequiredError as err:
                _LOGGER.warning(
                    "Reconnect aborted because panel linking is required: %s", err
                )
                return
            except (
                ConfigEntryNotReady,
                Elke27ConnectionError,
                Elke27DisconnectedError,
                Elke27TimeoutError,
                OSError,
            ) as err:
                _LOGGER.debug("Reconnect attempt failed: %s", err)
            else:
                self._reconnect_attempts = 0
                return
            self._reconnect_attempts += 1
            delay = min(300, 2 ** min(self._reconnect_attempts, 9))
            _LOGGER.debug(
                "Reconnect attempt %s sleeping for %s seconds",
                self._reconnect_attempts,
                delay,
            )
            await asyncio.sleep(delay)


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


def _set_client_identity(client: Elke27Client, client_identity: dict[str, str]) -> None:
    """Set the client identity used for future connects."""
    client.set_client_identity(client_identity)


def _connection_state(event: Any) -> bool | None:
    if isinstance(event, dict):
        event_type = event.get("event_type") or event.get("type")
        value = (
            event_type.value
            if isinstance(event_type, Enum)
            else str(event_type).lower()
            if event_type is not None
            else None
        )
        if value == "connection":
            data = event.get("data")
            if isinstance(data, dict):
                connected = data.get("connected")
                if isinstance(connected, bool):
                    return connected
        if value == "disconnected":
            return False
        if value == "ready":
            return True
        return None
    if hasattr(event, "event_type"):
        event_type = event.event_type
        value = (
            event_type.value
            if isinstance(event_type, Enum)
            else str(event_type).lower()
        )
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
