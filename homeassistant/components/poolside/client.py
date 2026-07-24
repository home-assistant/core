"""Runtime connection manager for the Poolside controller."""

import asyncio
from collections.abc import Callable, Iterable
import json
import random
from typing import Any
from uuid import uuid4

import aiohttp

from .const import (
    LOGGER,
    PING_INTERVAL,
    PING_TIMEOUT,
    RECONNECT_INITIAL_DELAY,
    RECONNECT_MAX_DELAY,
    SITE_MODE_FIELD,
    # STATUS_REFRESH_INTERVAL,  # periodic re-sync disabled for now, see below
)
from .models import (
    PoolsideControl,
    PoolsideDevice,
    PoolsideSite,
    parse_control_layout,
    parse_pool_devices,
)
from .noise_transport import NoiseSession, NoiseTransportError


class PoolsideConnectionError(Exception):
    """Raised when the controller cannot be reached or the handshake fails."""


class PoolsideAuthError(Exception):
    """Raised when the controller no longer trusts this client's key.

    Recovering requires re-pairing (config entry reauth).
    """


class PoolsideCommandError(Exception):
    """Raised when the controller rejects a JSON-RPC request."""


ConnectionListener = Callable[[bool], None]
StatusListener = Callable[[], None]


class PoolsideClient:
    """Owns the encrypted websocket connection to a Poolside controller."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        client_private_key: bytes,
        controller_public_key: bytes,
        controller_uuid: str,
    ) -> None:
        """Initialize the client with pinned identities; does not connect yet."""
        self._session = session
        self._host = host
        self._port = port
        self._client_private_key = client_private_key
        self._pinned_controller_public_key = controller_public_key
        self.controller_uuid = controller_uuid
        self.site_uuid: str | None = None

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._noise: NoiseSession | None = None
        self._write_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._status: dict[str, dict[str, Any]] = {}
        self._status_listeners: dict[str, list[StatusListener]] = {}
        self._connection_listeners: list[ConnectionListener] = []
        self._connected = False
        self._closing = False
        self._receive_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._ping_task: asyncio.Task[None] | None = None
        # self._status_refresh_task: asyncio.Task[None] | None = None
        self._ready_event = asyncio.Event()
        self._auth_failure_callback: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        """Return whether the controller connection is currently up."""
        return self._connected

    def set_auth_failure_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when the controller revokes this client."""
        self._auth_failure_callback = callback

    async def async_connect(self) -> None:
        """Open the socket, perform the Noise handshake, and wait for readiness."""
        self._closing = False
        await self._async_connect_once()
        self._reconnect_task = asyncio.ensure_future(self._async_reconnect_loop())

    async def async_disconnect(self) -> None:
        """Tear down the connection and stop reconnecting."""
        self._closing = True
        for task in (
            self._reconnect_task,
            self._receive_task,
            self._ping_task,
            # self._status_refresh_task,
        ):
            if task is not None:
                task.cancel()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._set_connected(False)

    async def _async_connect_once(self) -> None:
        """Perform a single connection attempt: handshake, verify, wait for ready."""
        try:
            ws = await self._session.ws_connect(f"ws://{self._host}:{self._port}/")
        except aiohttp.ClientError as err:
            raise PoolsideConnectionError(str(err)) from err

        noise = NoiseSession(self._client_private_key)
        try:
            remote_static = await noise.handshake(ws)
        except (NoiseTransportError, aiohttp.ClientError) as err:
            await ws.close()
            raise PoolsideConnectionError(str(err)) from err

        if remote_static != self._pinned_controller_public_key:
            await ws.close()
            raise PoolsideAuthError(
                "Controller's static key does not match the pinned key"
            )

        if self._ping_task is not None:
            self._ping_task.cancel()
        # if self._status_refresh_task is not None:
        #     self._status_refresh_task.cancel()

        self._ws = ws
        self._noise = noise
        self._status = {}
        self._ready_event = asyncio.Event()
        self._receive_task = asyncio.ensure_future(self._async_receive_loop(ws, noise))

        ready_wait = asyncio.ensure_future(self._ready_event.wait())
        done, _pending = await asyncio.wait(
            {ready_wait, self._receive_task},
            timeout=PING_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if ready_wait not in done:
            ready_wait.cancel()
            if self._receive_task in done:
                if ws.close_code == 1008:
                    raise PoolsideAuthError(
                        "Controller rejected this client (not paired or revoked)"
                    )
                raise PoolsideConnectionError("Connection closed before ready")
            await ws.close()
            raise PoolsideConnectionError("Controller did not send a ready message")

        await self.async_refresh_status()
        self._ping_task = asyncio.ensure_future(self._async_ping_loop())
        # Periodic re-sync disabled for now; may re-enable later.
        # self._status_refresh_task = asyncio.ensure_future(
        #     self._async_status_refresh_loop()
        # )
        self._set_connected(True)

    async def _async_reconnect_loop(self) -> None:
        """Watch the receive loop and reconnect with jittered backoff on drop."""
        delay = RECONNECT_INITIAL_DELAY
        while not self._closing:
            if self._receive_task is not None:
                await self._receive_task
            if self._closing:
                return
            self._set_connected(False)
            await asyncio.sleep(delay + random.uniform(0, delay))
            delay = min(delay * 2, RECONNECT_MAX_DELAY)
            try:
                await self._async_connect_once()
            except PoolsideAuthError:
                if self._auth_failure_callback is not None:
                    self._auth_failure_callback()
                return
            except PoolsideConnectionError as err:
                LOGGER.debug("Reconnect attempt failed: %s", err)
                continue
            delay = RECONNECT_INITIAL_DELAY

    async def _async_ping_loop(self) -> None:
        """Send a keepalive ping every PING_INTERVAL seconds."""
        while True:
            await asyncio.sleep(PING_INTERVAL)
            try:
                async with asyncio.timeout(PING_TIMEOUT):
                    await self.async_send_request("Site.ping", {})
            except TimeoutError, PoolsideConnectionError, PoolsideCommandError:
                if self._ws is not None and not self._ws.closed:
                    await self._ws.close()
                return

    # async def _async_status_refresh_loop(self) -> None:
    #     """Re-fetch the full status snapshot every STATUS_REFRESH_INTERVAL seconds.
    #
    #     A safety net in case an incremental setStatus push was ever missed;
    #     async_refresh_status already handles its own errors.
    #     """
    #     while True:
    #         await asyncio.sleep(STATUS_REFRESH_INTERVAL)
    #         await self.async_refresh_status()

    async def _async_receive_loop(
        self, ws: aiohttp.ClientWebSocketResponse, noise: NoiseSession
    ) -> None:
        """Read, decrypt, and dispatch messages until the socket closes."""
        try:
            async for msg in ws:
                if msg.type is aiohttp.WSMsgType.BINARY:
                    try:
                        payload = noise.decrypt_message(msg.data)
                        self._dispatch(json.loads(payload))
                    except NoiseTransportError:
                        LOGGER.exception("Failed to decrypt message from controller")
                        break
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
        finally:
            self._fail_pending(PoolsideConnectionError("Connection lost"))
        if ws.close_code == 1008 and self._auth_failure_callback is not None:
            self._auth_failure_callback()

    def _dispatch(self, message: dict[str, Any]) -> None:
        """Route a decrypted JSON-RPC message to its handler."""
        if message.get("method") in ("Device.setStatus", "setStatus"):
            self._handle_status_push(message.get("params") or [])
            return
        if "id" in message and message["id"] in self._pending:
            future = self._pending.pop(message["id"])
            if future.done():
                return
            if "error" in message:
                future.set_exception(PoolsideCommandError(message["error"]))
            else:
                future.set_result(message.get("result"))
            return
        if message.get("type") == "ready":
            self._ready_event.set()

    def _handle_status_push(self, items: Iterable[dict[str, Any]]) -> None:
        changed_uuids: set[str] = set()
        for item in items:
            uuid = item.get("UUID")
            name = item.get("name")
            if uuid is None or name is None:
                continue
            value = item.get("value")
            LOGGER.debug("Status update: %s.%s = %r", uuid, name, value)
            self._status.setdefault(uuid, {})[name] = value
            changed_uuids.add(uuid)
        for uuid in changed_uuids:
            listeners = self._status_listeners.get(uuid, [])
            LOGGER.debug("Notifying %d listener(s) for %s", len(listeners), uuid)
            for listener in listeners:
                listener()

    def _set_connected(self, connected: bool) -> None:
        if connected == self._connected:
            return
        self._connected = connected
        for listener in list(self._connection_listeners):
            listener(connected)

    def _fail_pending(self, error: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    def get_status(self, control_uuid: str, field: str) -> Any | None:
        """Return the last known value of a named status field for a control."""
        return self._status.get(control_uuid, {}).get(field)

    def subscribe_status(
        self, control_uuid: str, listener: StatusListener
    ) -> Callable[[], None]:
        """Register a callback invoked whenever this control's status changes."""
        listeners = self._status_listeners.setdefault(control_uuid, [])
        listeners.append(listener)

        def unsubscribe() -> None:
            listeners.remove(listener)

        return unsubscribe

    def subscribe_connection(self, listener: ConnectionListener) -> Callable[[], None]:
        """Register a callback invoked whenever overall connectivity changes."""
        self._connection_listeners.append(listener)

        def unsubscribe() -> None:
            self._connection_listeners.remove(listener)

        return unsubscribe

    async def async_send_request(self, method: str, params: dict[str, Any]) -> Any:
        """Send a JSON-RPC request and wait for its response."""
        if self._ws is None or self._noise is None or self._ws.closed:
            raise PoolsideConnectionError("Not connected")

        request_id = str(uuid4())
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        payload = json.dumps(
            {"id": request_id, "jsonrpc": "2.0", "method": method, "params": params}
        ).encode()

        async with self._write_lock:
            try:
                await self._ws.send_bytes(self._noise.encrypt_message(payload))
            except (aiohttp.ClientError, NoiseTransportError) as err:
                self._pending.pop(request_id, None)
                raise PoolsideConnectionError(str(err)) from err

        return await future

    @property
    def site_mode(self) -> Any | None:
        """Return the controller's last reported site-wide Mode, if known.

        Requires the site UUID from a previous control-layout fetch; older
        controller firmware that reports no site UUID has no known mode.
        """
        if self.site_uuid is None:
            return None
        return self.get_status(self.site_uuid, SITE_MODE_FIELD)

    async def async_get_control_layout(
        self,
    ) -> tuple[PoolsideSite, list[PoolsideControl]]:
        """Fetch controls pre-wrapped into their groups from Site.getControlLayout."""
        result = await self.async_send_request("Site.getControlLayout", {})
        site, controls = parse_control_layout(result)
        self.site_uuid = site.uuid
        return site, controls

    async def async_get_pool_devices(self) -> list[PoolsideDevice]:
        """Fetch the physical pool devices via Site.getPoolDevices.

        Controller firmware that predates the method rejects the request,
        which surfaces as a PoolsideCommandError for the caller to treat as
        "no pool devices".
        """
        result = await self.async_send_request("Site.getPoolDevices", {})
        return parse_pool_devices(result)

    async def async_refresh_status(self) -> None:
        """Fetch every current status item via Device.getStatus and apply it.

        Called on every (re)connect so controls nobody has interacted with
        yet - and that haven't happened to receive an incremental setStatus
        push - still get populated immediately instead of sitting unknown
        until someone touches them from the HA side.
        """
        try:
            items = await self.async_send_request("Device.getStatus", {})
        except PoolsideConnectionError, PoolsideCommandError:
            LOGGER.exception("Failed to fetch the initial status snapshot")
            return
        self._handle_status_push(items or [])

    async def async_set_desired_state(self, control_uuid: str, **fields: Any) -> None:
        """Write a control's desired state via Device.setDesiredState2.

        The controller confirms this via its own setStatus pushes (and the
        next getStatus snapshot); this also records the written fields as an
        optimistic echo (keyed by the control's own UUID) so entities update
        immediately, before that confirmation arrives.
        """
        await self.async_send_request(
            "Device.setDesiredState2",
            {
                "BatchUUID": str(uuid4()),
                "DesiredStates": [{"ControlUUID": control_uuid, **fields}],
            },
        )
        self._handle_status_push(
            [
                {"UUID": control_uuid, "name": name, "value": value}
                for name, value in fields.items()
            ]
        )
