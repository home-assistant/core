"""View to accept incoming websocket connection."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
import datetime as dt
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohttp import WSMsgType, web
import async_timeout

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util.json import json_loads

from .auth import AuthPhase, auth_required_message
from .const import (
    DATA_CONNECTIONS,
    MAX_PENDING_MSG,
    PENDING_MSG_PEAK,
    PENDING_MSG_PEAK_TIME,
    SIGNAL_WEBSOCKET_CONNECTED,
    SIGNAL_WEBSOCKET_DISCONNECTED,
    URL,
)
from .error import Disconnect
from .messages import message_to_json
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
        return await WebSocketHandler(request.app["hass"], request).async_handle()


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
    )

    def __init__(self, hass: HomeAssistant, request: web.Request) -> None:
        """Initialize an active connection."""
        self._hass = hass
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
        self._message_queue: deque[str | None] = deque()
        self._ready_future: asyncio.Future[None] | None = None

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

    async def _writer(self) -> None:
        """Write outgoing messages."""
        # Variables are set locally to avoid lookups in the loop
        message_queue = self._message_queue
        logger = self._logger
        wsock = self._wsock
        send_str = wsock.send_str
        loop = self._hass.loop
        debug = logger.debug
        is_enabled_for = logger.isEnabledFor
        logging_debug = logging.DEBUG
        # Exceptions if Socket disconnected or cancelled by connection handler
        try:
            while not wsock.closed:
                if (messages_remaining := len(message_queue)) == 0:
                    self._ready_future = loop.create_future()
                    await self._ready_future
                    messages_remaining = len(message_queue)

                # A None message is used to signal the end of the connection
                if (message := message_queue.popleft()) is None:
                    return

                debug_enabled = is_enabled_for(logging_debug)
                messages_remaining -= 1

                if (
                    not messages_remaining
                    or not (connection := self._connection)
                    or not connection.can_coalesce
                ):
                    if debug_enabled:
                        debug("%s: Sending %s", self.description, message)
                    await send_str(message)
                    continue

                messages: list[str] = [message]
                while messages_remaining:
                    # A None message is used to signal the end of the connection
                    if (message := message_queue.popleft()) is None:
                        return
                    messages.append(message)
                    messages_remaining -= 1

                joined_messages = ",".join(messages)
                coalesced_messages = f"[{joined_messages}]"
                if debug_enabled:
                    debug("%s: Sending %s", self.description, coalesced_messages)
                await send_str(coalesced_messages)
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
    def _send_message(self, message: str | dict[str, Any]) -> None:
        """Send a message to the client.

        Closes connection if the client is not reading the messages.

        Async friendly.
        """
        if self._closing:
            # Connection is cancelled, don't flood logs about exceeding
            # max pending messages.
            return

        if isinstance(message, dict):
            message = message_to_json(message)

        message_queue = self._message_queue
        queue_size_before_add = len(message_queue)
        if queue_size_before_add >= MAX_PENDING_MSG:
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

        message_queue.append(message)
        ready_future = self._ready_future
        if ready_future and not ready_future.done():
            ready_future.set_result(None)

        peak_checker_active = self._peak_checker_unsub is not None

        if queue_size_before_add <= PENDING_MSG_PEAK:
            if peak_checker_active:
                self._cancel_peak_checker()
            return

        if not peak_checker_active:
            self._peak_checker_unsub = async_call_later(
                self._hass, PENDING_MSG_PEAK_TIME, self._check_write_peak
            )

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

    async def async_handle(self) -> web.WebSocketResponse:
        """Handle a websocket response."""
        request = self._request
        wsock = self._wsock
        logger = self._logger
        debug = logger.debug
        hass = self._hass
        is_enabled_for = logger.isEnabledFor
        logging_debug = logging.DEBUG

        try:
            async with async_timeout.timeout(10):
                await wsock.prepare(request)
        except asyncio.TimeoutError:
            self._logger.warning("Timeout preparing request from %s", request.remote)
            return wsock

        debug("%s: Connected from %s", self.description, request.remote)
        self._handle_task = asyncio.current_task()

        @callback
        def handle_hass_stop(event: Event) -> None:
            """Cancel this connection."""
            self._cancel()

        unsub_stop = hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_hass_stop)

        # As the webserver is now started before the start
        # event we do not want to block for websocket responses
        self._writer_task = asyncio.create_task(self._writer())

        auth = AuthPhase(logger, hass, self._send_message, self._cancel, request)
        connection = None
        disconnect_warn = None

        try:
            self._send_message(auth_required_message())

            # Auth Phase
            try:
                async with async_timeout.timeout(10):
                    msg = await wsock.receive()
            except asyncio.TimeoutError as err:
                disconnect_warn = "Did not receive auth message within 10 seconds"
                raise Disconnect from err

            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                raise Disconnect

            if msg.type != WSMsgType.TEXT:
                disconnect_warn = "Received non-Text message."
                raise Disconnect

            try:
                auth_msg_data = json_loads(msg.data)
            except ValueError as err:
                disconnect_warn = "Received invalid JSON."
                raise Disconnect from err

            if is_enabled_for(logging_debug):
                debug("%s: Received %s", self.description, auth_msg_data)
            connection = await auth.async_handle(auth_msg_data)
            self._connection = connection
            hass.data[DATA_CONNECTIONS] = hass.data.get(DATA_CONNECTIONS, 0) + 1
            async_dispatcher_send(hass, SIGNAL_WEBSOCKET_CONNECTED)

            self._authenticated = True
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
            wsock._writer._limit = 2**20  # type: ignore[union-attr] # pylint: disable=protected-access
            async_handle_str = connection.async_handle
            async_handle_binary = connection.async_handle_binary

            # Command phase
            while not wsock.closed:
                msg = await wsock.receive()

                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                    break

                if msg.type == WSMsgType.BINARY:
                    if len(msg.data) < 1:
                        disconnect_warn = "Received invalid binary message."
                        break
                    handler = msg.data[0]
                    payload = msg.data[1:]
                    async_handle_binary(handler, payload)
                    continue

                if msg.type != WSMsgType.TEXT:
                    disconnect_warn = "Received non-Text message."
                    break

                try:
                    command_msg_data = json_loads(msg.data)
                except ValueError:
                    disconnect_warn = "Received invalid JSON."
                    break

                if is_enabled_for(logging_debug):
                    debug("%s: Received %s", self.description, command_msg_data)

                if not isinstance(command_msg_data, list):
                    async_handle_str(command_msg_data)
                    continue

                for split_msg in command_msg_data:
                    async_handle_str(split_msg)

        except asyncio.CancelledError:
            debug("%s: Connection cancelled", self.description)
            raise

        except Disconnect as ex:
            debug("%s: Connection closed by client: %s", self.description, ex)

        except Exception:  # pylint: disable=broad-except
            self._logger.exception(
                "%s: Unexpected error inside websocket API", self.description
            )

        finally:
            unsub_stop()

            self._cancel_peak_checker()

            if connection is not None:
                connection.async_handle_close()

            self._closing = True

            self._message_queue.append(None)
            if self._ready_future and not self._ready_future.done():
                self._ready_future.set_result(None)

            # If the writer gets canceled we still need to close the websocket
            # so we have another finally block to make sure we close the websocket
            # if the writer gets canceled.
            try:
                await self._writer_task
            finally:
                try:
                    # Make sure all error messages are written before closing
                    await wsock.close()
                finally:
                    if disconnect_warn is None:
                        debug("%s: Disconnected", self.description)
                    else:
                        self._logger.warning(
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

        return wsock
