"""View to accept incoming websocket connection."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
import datetime as dt
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohttp import WSMsgType, web
from aiohttp.http_websocket import WebSocketWriter

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.json import json_loads

from .auth import AUTH_REQUIRED_MESSAGE, AuthPhase
from .const import (
    DATA_CONNECTIONS,
    MAX_PENDING_MSG,
    PENDING_MSG_MAX_FORCE_READY,
    PENDING_MSG_PEAK,
    PENDING_MSG_PEAK_TIME,
    SIGNAL_WEBSOCKET_CONNECTED,
    SIGNAL_WEBSOCKET_DISCONNECTED,
    URL,
)
from .error import Disconnect
from .messages import message_to_json_bytes
from .util import describe_request

if TYPE_CHECKING:
    from .connection import ActiveConnection


_WS_LOGGER: Final = logging.getLogger(f"{__name__}.connection")


class WebsocketAPIView(HomeAssistantView):
    """View to serve a websockets endpoint."""

    name: str = "websocketapi"
    url: str = URL
    requires_auth: bool = False

    async def get(self, request: web.Request) -> web.WebSocketResponse:
        """Handle an incoming websocket connection."""
        return await WebSocketHandler(request.app[KEY_HASS], request).async_handle()


class WebSocketAdapter(logging.LoggerAdapter):
    """Add connection id to websocket messages."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Add connid to websocket log messages."""
        assert self.extra is not None
        return f'[{self.extra["connid"]}] {msg}', kwargs


class WebSocketHandler:
    """Handle an active websocket client connection."""

    __slots__ = (
        "_hass",
        "_loop",
        "_request",
        "_wsock",
        "_handle_task",
        "_writer_task",
        "_closing",
        "_authenticated",
        "_logger",
        "_peak_checker_unsub",
        "_connection",
        "_message_queue",
        "_ready_future",
        "_release_ready_queue_size",
    )

    def __init__(self, hass: HomeAssistant, request: web.Request) -> None:
        """Initialize an active connection."""
        self._hass = hass
        self._loop = hass.loop
        self._request: web.Request = request
        self._wsock = web.WebSocketResponse(heartbeat=55)
        self._handle_task: asyncio.Task | None = None
        self._writer_task: asyncio.Task | None = None
        self._closing: bool = False
        self._authenticated: bool = False
        self._logger = WebSocketAdapter(_WS_LOGGER, {"connid": id(self)})
        self._peak_checker_unsub: Callable[[], None] | None = None
        self._connection: ActiveConnection | None = None

        # The WebSocketHandler has a single consumer and path
        # to where messages are queued. This allows the implementation
        # to use a deque and an asyncio.Future to avoid the overhead of
        # an asyncio.Queue.
        self._message_queue: deque[bytes] = deque()
        self._ready_future: asyncio.Future[int] | None = None
        self._release_ready_queue_size: int = 0

    def __repr__(self) -> str:
        """Return the representation."""
        return (
            "<WebSocketHandler "
            f"closing={self._closing} "
            f"authenticated={self._authenticated} "
            f"description={self.description}>"
        )

    @property
    def description(self) -> str:
        """Return a description of the connection."""
        if connection := self._connection:
            return connection.get_description(self._request)
        if request := self._request:
            return describe_request(request)
        return "finished connection"

    async def _writer(
        self,
        connection: ActiveConnection,
        send_bytes_text: Callable[[bytes], Coroutine[Any, Any, None]],
    ) -> None:
        """Write outgoing messages."""
        # Variables are set locally to avoid lookups in the loop
        message_queue = self._message_queue
        logger = self._logger
        wsock = self._wsock
        loop = self._loop
        is_debug_log_enabled = partial(logger.isEnabledFor, logging.DEBUG)
        debug = logger.debug
        can_coalesce = connection.can_coalesce
        ready_message_count = len(message_queue)
        # Exceptions if Socket disconnected or cancelled by connection handler
        try:
            while not wsock.closed:
                if not message_queue:
                    self._ready_future = loop.create_future()
                    ready_message_count = await self._ready_future

                if self._closing:
                    return

                if not can_coalesce:
                    # coalesce may be enabled later in the connection
                    can_coalesce = connection.can_coalesce

                if not can_coalesce or ready_message_count == 1:
                    message = message_queue.popleft()
                    if is_debug_log_enabled():
                        debug("%s: Sending %s", self.description, message)
                    await send_bytes_text(message)
                    continue

                coalesced_messages = b"".join((b"[", b",".join(message_queue), b"]"))
                message_queue.clear()
                if is_debug_log_enabled():
                    debug("%s: Sending %s", self.description, coalesced_messages)
                await send_bytes_text(coalesced_messages)
        except asyncio.CancelledError:
            debug("%s: Writer cancelled", self.description)
            raise
        except (RuntimeError, ConnectionResetError) as ex:
            debug("%s: Unexpected error in writer: %s", self.description, ex)
        finally:
            debug("%s: Writer done", self.description)
            # Clean up the peak checker when we shut down the writer
            self._cancel_peak_checker()

    @callback
    def _cancel_peak_checker(self) -> None:
        """Cancel the peak checker."""
        if self._peak_checker_unsub is not None:
            self._peak_checker_unsub()
            self._peak_checker_unsub = None

    @callback
    def _send_message(self, message: str | bytes | dict[str, Any]) -> None:
        """Queue sending a message to the client.

        Closes connection if the client is not reading the messages.

        Async friendly.
        """
        if self._closing:
            # Connection is cancelled, don't flood logs about exceeding
            # max pending messages.
            return

        if type(message) is not bytes:  # noqa: E721
            if isinstance(message, dict):
                message = message_to_json_bytes(message)
            elif isinstance(message, str):
                message = message.encode("utf-8")

        message_queue = self._message_queue
        message_queue.append(message)
        if (queue_size_after_add := len(message_queue)) >= MAX_PENDING_MSG:
            self._logger.error(
                (
                    "%s: Client unable to keep up with pending messages. Reached %s pending"
                    " messages. The system's load is too high or an integration is"
                    " misbehaving; Last message was: %s"
                ),
                self.description,
                MAX_PENDING_MSG,
                message,
            )
            self._cancel()
            return

        if self._release_ready_queue_size == 0:
            # Try to coalesce more messages to reduce the number of writes
            self._release_ready_queue_size = queue_size_after_add
            self._loop.call_soon(self._release_ready_future_or_reschedule)

        peak_checker_active = self._peak_checker_unsub is not None

        if queue_size_after_add <= PENDING_MSG_PEAK:
            if peak_checker_active:
                self._cancel_peak_checker()
            return

        if not peak_checker_active:
            self._peak_checker_unsub = async_call_later(
                self._hass, PENDING_MSG_PEAK_TIME, self._check_write_peak
            )

    @callback
    def _release_ready_future_or_reschedule(self) -> None:
        """Release the ready future or reschedule.

        We will release the ready future if the queue did not grow since the
        last time we tried to release the ready future.

        If we reach PENDING_MSG_MAX_FORCE_READY, we will release the ready future
        immediately so avoid the coalesced messages from growing too large.
        """
        if not (ready_future := self._ready_future) or not (
            queue_size := len(self._message_queue)
        ):
            self._release_ready_queue_size = 0
            return
        # If we are below the max pending to force ready, and there are new messages
        # in the queue since the last time we tried to release the ready future, we
        # try again later so we can coalesce more messages.
        if queue_size > self._release_ready_queue_size < PENDING_MSG_MAX_FORCE_READY:
            self._release_ready_queue_size = queue_size
            self._loop.call_soon(self._release_ready_future_or_reschedule)
            return
        self._release_ready_queue_size = 0
        if not ready_future.done():
            ready_future.set_result(queue_size)

    @callback
    def _check_write_peak(self, _utc_time: dt.datetime) -> None:
        """Check that we are no longer above the write peak."""
        self._peak_checker_unsub = None

        if len(self._message_queue) < PENDING_MSG_PEAK:
            return

        self._logger.error(
            (
                "%s: Client unable to keep up with pending messages. Stayed over %s for %s"
                " seconds. The system's load is too high or an integration is"
                " misbehaving; Last message was: %s"
            ),
            self.description,
            PENDING_MSG_PEAK,
            PENDING_MSG_PEAK_TIME,
            self._message_queue[-1],
        )
        self._cancel()

    @callback
    def _cancel(self) -> None:
        """Cancel the connection."""
        self._closing = True
        self._cancel_peak_checker()
        if self._handle_task is not None:
            self._handle_task.cancel()
        if self._writer_task is not None:
            self._writer_task.cancel()

    @callback
    def _async_handle_hass_stop(self, event: Event) -> None:
        """Cancel this connection."""
        self._cancel()

    async def async_handle(self) -> web.WebSocketResponse:
        """Handle a websocket response."""
        request = self._request
        wsock = self._wsock
        logger = self._logger
        hass = self._hass

        try:
            async with asyncio.timeout(10):
                await wsock.prepare(request)
        except ConnectionResetError:
            # Likely the client disconnected before we prepared the websocket
            logger.debug(
                "%s: Connection reset by peer while preparing WebSocket",
                self.description,
            )
            return wsock
        except TimeoutError:
            logger.warning("Timeout preparing request from %s", request.remote)
            return wsock

        logger.debug("%s: Connected from %s", self.description, request.remote)
        self._handle_task = asyncio.current_task()

        unsub_stop = hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._async_handle_hass_stop
        )

        writer = wsock._writer  # noqa: SLF001
        if TYPE_CHECKING:
            assert writer is not None

        send_bytes_text = partial(writer.send, binary=False)
        auth = AuthPhase(
            logger, hass, self._send_message, self._cancel, request, send_bytes_text
        )
        connection: ActiveConnection | None = None
        disconnect_warn: str | None = None

        try:
            connection = await self._async_handle_auth_phase(auth, send_bytes_text)
            self._async_increase_writer_limit(writer)
            await self._async_websocket_command_phase(connection, send_bytes_text)
        except asyncio.CancelledError:
            logger.debug("%s: Connection cancelled", self.description)
            raise
        except Disconnect as ex:
            if disconnect_msg := str(ex):
                disconnect_warn = disconnect_msg

            logger.debug("%s: Connection closed by client: %s", self.description, ex)
        except Exception:
            logger.exception(
                "%s: Unexpected error inside websocket API", self.description
            )
        finally:
            unsub_stop()

            self._cancel_peak_checker()

            if connection is not None:
                connection.async_handle_close()

            self._closing = True
            if self._ready_future and not self._ready_future.done():
                self._ready_future.set_result(len(self._message_queue))

            await self._async_cleanup_writer_and_close(disconnect_warn, connection)

        return wsock

    async def _async_handle_auth_phase(
        self,
        auth: AuthPhase,
        send_bytes_text: Callable[[bytes], Coroutine[Any, Any, None]],
    ) -> ActiveConnection:
        """Handle the auth phase of the websocket connection."""
        await send_bytes_text(AUTH_REQUIRED_MESSAGE)

        # Auth Phase
        try:
            msg = await self._wsock.receive(10)
        except TimeoutError as err:
            raise Disconnect("Did not receive auth message within 10 seconds") from err

        if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
            raise Disconnect("Received close message during auth phase")

        if msg.type is not WSMsgType.TEXT:
            raise Disconnect("Received non-Text message during auth phase")

        try:
            auth_msg_data = json_loads(msg.data)
        except ValueError as err:
            raise Disconnect("Received invalid JSON during auth phase") from err

        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("%s: Received %s", self.description, auth_msg_data)
        connection = await auth.async_handle(auth_msg_data)
        # As the webserver is now started before the start
        # event we do not want to block for websocket responses
        #
        # We only start the writer queue after the auth phase is completed
        # since there is no need to queue messages before the auth phase
        self._connection = connection
        self._writer_task = create_eager_task(self._writer(connection, send_bytes_text))
        self._hass.data[DATA_CONNECTIONS] = self._hass.data.get(DATA_CONNECTIONS, 0) + 1
        async_dispatcher_send(self._hass, SIGNAL_WEBSOCKET_CONNECTED)

        self._authenticated = True
        return connection

    @callback
    def _async_increase_writer_limit(self, writer: WebSocketWriter) -> None:
        #
        #
        # Our websocket implementation is backed by a deque
        #
        # As back-pressure builds, the queue will back up and use more memory
        # until we disconnect the client when the queue size reaches
        # MAX_PENDING_MSG. When we are generating a high volume of websocket messages,
        # we hit a bottleneck in aiohttp where it will wait for
        # the buffer to drain before sending the next message and messages
        # start backing up in the queue.
        #
        # https://github.com/aio-libs/aiohttp/issues/1367 added drains
        # to the websocket writer to handle malicious clients and network issues.
        # The drain causes multiple problems for us since the buffer cannot be
        # drained fast enough when we deliver a high volume or large messages:
        #
        # - We end up disconnecting the client. The client will then reconnect,
        # and the cycle repeats itself, which results in a significant amount of
        # CPU usage.
        #
        # - Messages latency increases because messages cannot be moved into
        # the TCP buffer because it is blocked waiting for the drain to happen because
        # of the low default limit of 16KiB. By increasing the limit, we instead
        # rely on the underlying TCP buffer and stack to deliver the messages which
        # can typically happen much faster.
        #
        # After the auth phase is completed, and we are not concerned about
        # the user being a malicious client, we set the limit to force a drain
        # to 1MiB. 1MiB is the maximum expected size of the serialized entity
        # registry, which is the largest message we usually send.
        #
        # https://github.com/aio-libs/aiohttp/commit/b3c80ee3f7d5d8f0b8bc27afe52e4d46621eaf99
        # added a way to set the limit, but there is no way to actually
        # reach the code to set the limit, so we have to set it directly.
        #
        writer._limit = 2**20  # noqa: SLF001

    async def _async_websocket_command_phase(
        self,
        connection: ActiveConnection,
        send_bytes_text: Callable[[bytes], Coroutine[Any, Any, None]],
    ) -> None:
        """Handle the command phase of the websocket connection."""
        wsock = self._wsock
        async_handle_str = connection.async_handle
        async_handle_binary = connection.async_handle_binary
        _debug_enabled = partial(self._logger.isEnabledFor, logging.DEBUG)

        # Command phase
        while not wsock.closed:
            msg = await wsock.receive()

            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                break

            if msg.type is WSMsgType.BINARY:
                if len(msg.data) < 1:
                    raise Disconnect("Received invalid binary message.")

                handler = msg.data[0]
                payload = msg.data[1:]
                async_handle_binary(handler, payload)
                continue

            if msg.type is not WSMsgType.TEXT:
                raise Disconnect("Received non-Text message.")

            try:
                command_msg_data = json_loads(msg.data)
            except ValueError as ex:
                raise Disconnect("Received invalid JSON.") from ex

            if _debug_enabled():
                self._logger.debug(
                    "%s: Received %s", self.description, command_msg_data
                )

            # command_msg_data is always deserialized from JSON as a list
            if type(command_msg_data) is not list:  # noqa: E721
                async_handle_str(command_msg_data)
                continue

            for split_msg in command_msg_data:
                async_handle_str(split_msg)

    async def _async_cleanup_writer_and_close(
        self, disconnect_warn: str | None, connection: ActiveConnection | None
    ) -> None:
        """Cleanup the writer and close the websocket."""
        # If the writer gets canceled we still need to close the websocket
        # so we have another finally block to make sure we close the websocket
        # if the writer gets canceled.
        wsock = self._wsock
        hass = self._hass
        logger = self._logger
        try:
            if self._writer_task:
                await self._writer_task
        finally:
            try:
                # Make sure all error messages are written before closing
                await wsock.close()
            finally:
                if disconnect_warn is None:
                    logger.debug("%s: Disconnected", self.description)
                else:
                    logger.warning(
                        "%s: Disconnected: %s", self.description, disconnect_warn
                    )

                if connection is not None:
                    hass.data[DATA_CONNECTIONS] -= 1
                    self._connection = None

                async_dispatcher_send(hass, SIGNAL_WEBSOCKET_DISCONNECTED)

                # Break reference cycles to make sure GC can happen sooner
                self._wsock = None  # type: ignore[assignment]
                self._request = None  # type: ignore[assignment]
                self._hass = None  # type: ignore[assignment]
                self._logger = None  # type: ignore[assignment]
                self._message_queue = None  # type: ignore[assignment]
                self._handle_task = None
                self._writer_task = None
                self._ready_future = None
