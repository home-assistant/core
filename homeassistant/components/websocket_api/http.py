"""View to accept incoming websocket connection."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
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
from homeassistant.helpers.json import json_loads

from .auth import AuthPhase, auth_required_message
from .const import (
    CANCELLATION_ERRORS,
    DATA_CONNECTIONS,
    FEATURE_COALESCE_MESSAGES,
    MAX_PENDING_MSG,
    PENDING_MSG_PEAK,
    PENDING_MSG_PEAK_TIME,
    SIGNAL_WEBSOCKET_CONNECTED,
    SIGNAL_WEBSOCKET_DISCONNECTED,
    URL,
)
from .error import Disconnect
from .messages import message_to_json

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
        return f'[{self.extra["connid"]}] {msg}', kwargs


class WebSocketHandler:
    """Handle an active websocket client connection."""

    def __init__(self, hass: HomeAssistant, request: web.Request) -> None:
        """Initialize an active connection."""
        self.hass = hass
        self.request = request
        self.wsock = web.WebSocketResponse(heartbeat=55)
        self._to_write: asyncio.Queue = asyncio.Queue(maxsize=MAX_PENDING_MSG)
        self._handle_task: asyncio.Task | None = None
        self._writer_task: asyncio.Task | None = None
        self._logger = WebSocketAdapter(_WS_LOGGER, {"connid": id(self)})
        self._peak_checker_unsub: Callable[[], None] | None = None
        self.connection: ActiveConnection | None = None

    async def _writer(self) -> None:
        """Write outgoing messages."""
        # Exceptions if Socket disconnected or cancelled by connection handler
        to_write = self._to_write
        logger = self._logger
        wsock = self.wsock
        try:
            with suppress(RuntimeError, ConnectionResetError, *CANCELLATION_ERRORS):
                while not self.wsock.closed:
                    if (process := await to_write.get()) is None:
                        return
                    message = process if isinstance(process, str) else process()

                    if (
                        to_write.empty()
                        or not self.connection
                        or FEATURE_COALESCE_MESSAGES
                        not in self.connection.supported_features
                    ):
                        logger.debug("Sending %s", message)
                        await wsock.send_str(message)
                        continue

                    messages: list[str] = [message]
                    while not to_write.empty():
                        if (process := to_write.get_nowait()) is None:
                            return
                        messages.append(
                            process if isinstance(process, str) else process()
                        )

                    coalesced_messages = "[" + ",".join(messages) + "]"
                    self._logger.debug("Sending %s", coalesced_messages)
                    await self.wsock.send_str(coalesced_messages)
        finally:
            # Clean up the peaker checker when we shut down the writer
            if self._peak_checker_unsub is not None:
                self._peak_checker_unsub()
                self._peak_checker_unsub = None

    @callback
    def _send_message(self, message: str | dict[str, Any] | Callable[[], str]) -> None:
        """Send a message to the client.

        Closes connection if the client is not reading the messages.

        Async friendly.
        """
        if isinstance(message, dict):
            message = message_to_json(message)

        try:
            self._to_write.put_nowait(message)
        except asyncio.QueueFull:
            self._logger.error(
                "Client exceeded max pending messages [2]: %s", MAX_PENDING_MSG
            )

            self._cancel()

        if self._to_write.qsize() < PENDING_MSG_PEAK:
            if self._peak_checker_unsub:
                self._peak_checker_unsub()
                self._peak_checker_unsub = None
            return

        if self._peak_checker_unsub is None:
            self._peak_checker_unsub = async_call_later(
                self.hass, PENDING_MSG_PEAK_TIME, self._check_write_peak
            )

    @callback
    def _check_write_peak(self, _utc_time: dt.datetime) -> None:
        """Check that we are no longer above the write peak."""
        self._peak_checker_unsub = None

        if self._to_write.qsize() < PENDING_MSG_PEAK:
            return

        self._logger.error(
            "Client unable to keep up with pending messages. Stayed over %s for %s seconds. "
            "The system's load is too high or an integration is misbehaving",
            PENDING_MSG_PEAK,
            PENDING_MSG_PEAK_TIME,
        )
        self._cancel()

    @callback
    def _cancel(self) -> None:
        """Cancel the connection."""
        if self._handle_task is not None:
            self._handle_task.cancel()
        if self._writer_task is not None:
            self._writer_task.cancel()

    async def async_handle(self) -> web.WebSocketResponse:
        """Handle a websocket response."""
        request = self.request
        wsock = self.wsock
        try:
            async with async_timeout.timeout(10):
                await wsock.prepare(request)
        except asyncio.TimeoutError:
            self._logger.warning("Timeout preparing request from %s", request.remote)
            return wsock

        self._logger.debug("Connected from %s", request.remote)
        self._handle_task = asyncio.current_task()

        @callback
        def handle_hass_stop(event: Event) -> None:
            """Cancel this connection."""
            self._cancel()

        unsub_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, handle_hass_stop
        )

        # As the webserver is now started before the start
        # event we do not want to block for websocket responses
        self._writer_task = asyncio.create_task(self._writer())

        auth = AuthPhase(
            self._logger, self.hass, self._send_message, self._cancel, request
        )
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

            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING):
                raise Disconnect

            if msg.type != WSMsgType.TEXT:
                disconnect_warn = "Received non-Text message."
                raise Disconnect

            try:
                msg_data = msg.json(loads=json_loads)
            except ValueError as err:
                disconnect_warn = "Received invalid JSON."
                raise Disconnect from err

            self._logger.debug("Received %s", msg_data)
            self.connection = connection = await auth.async_handle(msg_data)
            self.hass.data[DATA_CONNECTIONS] = (
                self.hass.data.get(DATA_CONNECTIONS, 0) + 1
            )
            async_dispatcher_send(self.hass, SIGNAL_WEBSOCKET_CONNECTED)

            # Command phase
            while not wsock.closed:
                msg = await wsock.receive()

                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING):
                    break

                if msg.type != WSMsgType.TEXT:
                    disconnect_warn = "Received non-Text message."
                    break

                try:
                    msg_data = msg.json(loads=json_loads)
                except ValueError:
                    disconnect_warn = "Received invalid JSON."
                    break

                self._logger.debug("Received %s", msg_data)
                if not isinstance(msg_data, list):
                    connection.async_handle(msg_data)
                    continue

                for split_msg in msg_data:
                    connection.async_handle(split_msg)

        except asyncio.CancelledError:
            self._logger.info("Connection closed by client")

        except Disconnect:
            pass

        except Exception:  # pylint: disable=broad-except
            self._logger.exception("Unexpected error inside websocket API")

        finally:
            unsub_stop()

            if connection is not None:
                connection.async_handle_close()

            try:
                self._to_write.put_nowait(None)
                # Make sure all error messages are written before closing
                await self._writer_task
                await wsock.close()
            except asyncio.QueueFull:  # can be raised by put_nowait
                self._writer_task.cancel()

            finally:
                if disconnect_warn is None:
                    self._logger.debug("Disconnected")
                else:
                    self._logger.warning("Disconnected: %s", disconnect_warn)

                if connection is not None:
                    self.hass.data[DATA_CONNECTIONS] -= 1
                    self.connection = None

                async_dispatcher_send(self.hass, SIGNAL_WEBSOCKET_DISCONNECTED)

        return wsock
