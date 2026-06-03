"""Hub wrapper for the Elke27 client lifecycle."""

import asyncio
from collections.abc import Callable
import contextlib
import logging
from typing import Any

from elke27_lib import ArmMode, ClientConfig, LinkKeys, PanelSnapshot
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
from elke27_lib.types import CsmSnapshot

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import READY_TIMEOUT
from .identity import build_client_identity

_LOGGER = logging.getLogger(__name__)

_ARM_MODE_BY_NAME = {
    "ARMED_AWAY": ArmMode.ARMED_AWAY,
    "ARMED_CUSTOM_BYPASS": ArmMode.ARMED_AWAY,
    "ARMED_NIGHT": ArmMode.ARMED_NIGHT,
    "ARMED_STAY": ArmMode.ARMED_STAY,
}


def _raise_command_error(action: str, error: BaseException) -> None:
    """Raise a Home Assistant error for a failed client command."""
    detail = (
        getattr(error, "user_message", None)
        or getattr(error, "message", None)
        or str(error)
    )
    message = f"{action} failed: {detail}" if detail else f"{action} failed."
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
            try:
                link_keys = LinkKeys.from_json(self._link_keys_json)
            except (
                AttributeError,
                Elke27Error,
                KeyError,
                TypeError,
                ValueError,
            ) as err:
                msg = "Linking credentials are invalid"
                raise ConfigEntryAuthFailed(msg) from err
            client = Elke27Client(ClientConfig())
            client_identity = build_client_identity(self._client_id)
            _set_client_identity(client, client_identity)
            connection_unsubscribe: Callable[[], None] | None = None

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
                connection_unsubscribe = client.subscribe(self._handle_connection_event)
                self._resubscribe_typed_callbacks(client)
                self._connection_unsubscribe = connection_unsubscribe
                self._client = client
                if self._unavailable_logged:
                    _LOGGER.info("Panel connection restored")
                    self._unavailable_logged = False
            except asyncio.CancelledError:
                await asyncio.shield(
                    self._async_cleanup_failed_connect(client, connection_unsubscribe)
                )
                raise
            except Exception:
                await self._async_cleanup_failed_connect(client, connection_unsubscribe)
                raise

    async def async_disconnect(self) -> None:
        """Disconnect the client and unregister event handlers."""
        self._stopping = True
        async with self._connect_lock:
            if self._reconnect_task is not None:
                self._reconnect_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._reconnect_task
                self._reconnect_task = None
            await self._async_disconnect()

    async def _async_disconnect(self, *, log_unavailable: bool = True) -> None:
        """Disconnect the client and unregister event handlers."""
        was_connected = self._client is not None
        cancel_error: asyncio.CancelledError | None = None
        if self._connection_unsubscribe is not None:
            try:
                self._connection_unsubscribe()
            except asyncio.CancelledError as err:
                cancel_error = err
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Error while unsubscribing connection callback", exc_info=True
                )
            self._connection_unsubscribe = None
        if self._client is not None:
            try:
                await self._client.async_disconnect()
            except asyncio.CancelledError as err:
                cancel_error = err
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error while disconnecting client", exc_info=True)
        self._client = None
        try:
            self._clear_typed_subscriptions()
        except asyncio.CancelledError as err:
            cancel_error = err
        if was_connected and not self._stopping and log_unavailable:
            self._log_unavailable()
        if cancel_error is not None:
            raise cancel_error

    def get_snapshot(self) -> PanelSnapshot | None:
        """Return the latest client snapshot."""
        client = self._client
        if client is None:
            return None
        return client.get_snapshot()

    async def refresh_csm(self) -> CsmSnapshot:
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

        removed = False

        def _remove() -> None:
            nonlocal removed
            if removed:
                return
            removed = True
            self.unsubscribe_typed(listener)

        return _remove

    def unsubscribe_typed(self, listener: Callable[[Any], None]) -> bool:
        """Unsubscribe from typed client events."""
        if listener in self._typed_callbacks:
            unsubscribe = self._typed_callbacks.pop(listener)
            if unsubscribe is not None:
                _unsubscribe_callback(unsubscribe)
            return True
        return False

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

        arm_mode = _normalize_arm_mode(mode)

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

    def _resubscribe_typed_callbacks(self, client: Elke27Client) -> None:
        """Re-register typed callbacks on a new client connection."""
        if not self._typed_callbacks:
            return
        for cb in list(self._typed_callbacks):
            self._typed_callbacks[cb] = client.subscribe_typed(cb)

    def _clear_typed_subscriptions(self) -> None:
        """Clear typed subscriptions when the client disconnects."""
        cancel_error: asyncio.CancelledError | None = None
        for cb, unsubscribe in list(self._typed_callbacks.items()):
            if unsubscribe is not None:
                try:
                    _unsubscribe_callback(unsubscribe)
                except asyncio.CancelledError as err:
                    cancel_error = err
            self._typed_callbacks[cb] = None
        if cancel_error is not None:
            raise cancel_error

    async def _async_cleanup_connecting_client(
        self,
        client: Elke27Client,
        connection_unsubscribe: Callable[[], None] | None,
    ) -> None:
        """Clean up a client that failed before becoming the active client."""
        if connection_unsubscribe is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                connection_unsubscribe()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await client.async_disconnect()
        self._clear_typed_subscriptions()

    async def _async_cleanup_failed_connect(
        self,
        client: Elke27Client,
        connection_unsubscribe: Callable[[], None] | None,
    ) -> None:
        """Clean up one failed connection attempt."""
        if self._client is client:
            await self._async_disconnect(log_unavailable=False)
            return
        await self._async_cleanup_connecting_client(client, connection_unsubscribe)

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
        if connection_state is False:
            _LOGGER.debug("Panel disconnect event received; scheduling reconnect")
            self._hass.loop.call_soon_threadsafe(self._handle_disconnected)
        elif connection_state is True:
            self._hass.loop.call_soon_threadsafe(self._cancel_reconnect)

    @callback
    def _handle_disconnected(self) -> None:
        """Handle a panel disconnect on the Home Assistant event loop."""
        self._log_unavailable()
        self._schedule_reconnect()

    @callback
    def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempts when the panel disconnects."""
        if self._stopping:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        _LOGGER.debug("Creating reconnect task")
        task = self._hass.async_create_task(self._async_reconnect_loop())
        self._reconnect_task = task
        task.add_done_callback(self._finish_reconnect_task)

    @callback
    def _cancel_reconnect(self) -> None:
        """Cancel any scheduled reconnection attempts."""
        task = self._reconnect_task
        if task is None:
            return
        if task.done():
            self._finish_reconnect_task(task)
        else:
            task.cancel()
            task.add_done_callback(self._finish_reconnect_task)
        self._reconnect_attempts = 0

    @callback
    def _finish_reconnect_task(self, task: asyncio.Task[None]) -> None:
        """Consume reconnect task result and clear it when complete."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("Unexpected reconnect task failure")
        if self._reconnect_task is task:
            self._reconnect_task = None

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
            except (ConfigEntryAuthFailed, Elke27LinkRequiredError) as err:
                _LOGGER.warning(
                    "Reconnect aborted because panel authentication requires attention: %s",
                    err,
                )
                self._reconnect_attempts = 0
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
        self._reconnect_attempts = 0


def _set_client_identity(client: Elke27Client, client_identity: dict[str, str]) -> None:
    """Set the client identity used for future connects."""
    client.set_client_identity(client_identity)


def _unsubscribe_callback(unsubscribe: Callable[[], None]) -> None:
    """Call an unsubscribe callback while preserving cancellation."""
    try:
        unsubscribe()
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Error while unsubscribing callback", exc_info=True)


def _normalize_arm_mode(mode: Any) -> ArmMode:
    """Normalize supported Home Assistant arm modes to client arm modes."""
    if isinstance(mode, ArmMode):
        arm_mode = mode
    elif isinstance(mode, str):
        arm_mode = _ARM_MODE_BY_NAME.get(mode.upper())
    else:
        arm_mode = None
    if arm_mode in {
        ArmMode.ARMED_AWAY,
        ArmMode.ARMED_NIGHT,
        ArmMode.ARMED_STAY,
    }:
        return arm_mode
    msg = "Arm mode is not supported."
    raise HomeAssistantError(msg)


def _connection_state(event: Any) -> bool | None:
    """Return the connection state from a client connection event."""
    connected = getattr(event, "connected", None)
    return connected if isinstance(connected, bool) else None
