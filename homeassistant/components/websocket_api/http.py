"""View to accept incoming websocket connection."""
import asyncio
from contextlib import suppress
from functools import partial
import json
import logging

from aiohttp import web, WSMsgType
import async_timeout

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.json import JSONEncoder

from .const import (
    MAX_PENDING_MSG, CANCELLATION_ERRORS, URL, ERR_UNKNOWN_ERROR,
    SIGNAL_WEBSOCKET_CONNECTED, SIGNAL_WEBSOCKET_DISCONNECTED,
    DATA_CONNECTIONS)
from .auth import AuthPhase, auth_required_message
from .error import Disconnect
from .messages import error_message

JSON_DUMP = partial(json.dumps, cls=JSONEncoder, allow_nan=False)


class WebsocketAPIView(HomeAssistantView):
    """View to serve a websockets endpoint."""

    name = "websocketapi"
    url = URL
    requires_auth = False

    async def get(self, request):
        """Handle an incoming websocket connection."""
        return await WebSocketHandler(
            request.app['hass'], request).async_handle()


class WebSocketHandler:
    """Handle an active websocket client connection."""

    def __init__(self, hass, request):
        """Initialize an active connection."""
        self.hass = hass
        self.request = request
        self.wsock = None
        self._to_write = asyncio.Queue(maxsize=MAX_PENDING_MSG, loop=hass.loop)
        self._handle_task = None
        self._writer_task = None
        self._logger = logging.getLogger(
            "{}.connection.{}".format(__name__, id(self)))

    async def _writer(self):
        """Write outgoing messages."""
        # Exceptions if Socket disconnected or cancelled by connection handler
        with suppress(RuntimeError, ConnectionResetError,
                      *CANCELLATION_ERRORS):
            while not self.wsock.closed:
                message = await self._to_write.get()
                if message is None:
                    break
                self._logger.debug("Sending %s", message)
                try:
                    await self.wsock.send_json(message, dumps=JSON_DUMP)
                except (ValueError, TypeError) as err:
                    self._logger.error('Unable to serialize to JSON: %s\n%s',
                                       err, message)
                    await self.wsock.send_json(error_message(
                        message['id'], ERR_UNKNOWN_ERROR,
                        'Invalid JSON in response'))

    @callback
    def _send_message(self, message):
        """Send a message to the client.

        Closes connection if the client is not reading the messages.

        Async friendly.
        """
        try:
            self._to_write.put_nowait(message)
        except asyncio.QueueFull:
            self._logger.error("Client exceeded max pending messages [2]: %s",
                               MAX_PENDING_MSG)
            self._cancel()

    @callback
    def _cancel(self):
        """Cancel the connection."""
        self._handle_task.cancel()
        self._writer_task.cancel()

    async def async_handle(self):
        """Handle a websocket response."""
        request = self.request
        wsock = self.wsock = web.WebSocketResponse(heartbeat=55)
        await wsock.prepare(request)
        self._logger.debug("Connected")

        # Py3.7+
        if hasattr(asyncio, 'current_task'):
            # pylint: disable=no-member
            self._handle_task = asyncio.current_task()
        else:
            self._handle_task = asyncio.Task.current_task(loop=self.hass.loop)

        @callback
        def handle_hass_stop(event):
            """Cancel this connection."""
            self._cancel()

        unsub_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, handle_hass_stop)

        self._writer_task = self.hass.async_create_task(self._writer())

        auth = AuthPhase(self._logger, self.hass, self._send_message, request)
        connection = None
        disconnect_warn = None

        try:
            self._send_message(auth_required_message())

            # Auth Phase
            try:
                with async_timeout.timeout(10):
                    msg = await wsock.receive()
            except asyncio.TimeoutError:
                disconnect_warn = \
                    'Did not receive auth message within 10 seconds'
                raise Disconnect

            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING):
                raise Disconnect

            if msg.type != WSMsgType.TEXT:
                disconnect_warn = 'Received non-Text message.'
                raise Disconnect

            try:
                msg = msg.json()
            except ValueError:
                disconnect_warn = 'Received invalid JSON.'
                raise Disconnect

            self._logger.debug("Received %s", msg)
            connection = await auth.async_handle(msg)
            self.hass.data[DATA_CONNECTIONS] = \
                self.hass.data.get(DATA_CONNECTIONS, 0) + 1
            self.hass.helpers.dispatcher.async_dispatcher_send(
                SIGNAL_WEBSOCKET_CONNECTED)

            # Command phase
            while not wsock.closed:
                msg = await wsock.receive()

                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING):
                    break

                elif msg.type != WSMsgType.TEXT:
                    disconnect_warn = 'Received non-Text message.'
                    break

                try:
                    msg = msg.json()
                except ValueError:
                    disconnect_warn = 'Received invalid JSON.'
                    break

                self._logger.debug("Received %s", msg)
                connection.async_handle(msg)

        except asyncio.CancelledError:
            self._logger.info("Connection closed by client")

        except Disconnect:
            pass

        except Exception:  # pylint: disable=broad-except
            self._logger.exception("Unexpected error inside websocket API")

        finally:
            unsub_stop()

            if connection is not None:
                connection.async_close()

            try:
                self._to_write.put_nowait(None)
                # Make sure all error messages are written before closing
                await self._writer_task
            except asyncio.QueueFull:
                self._writer_task.cancel()

            await wsock.close()

            if disconnect_warn is None:
                self._logger.debug("Disconnected")
            else:
                self._logger.warning("Disconnected: %s", disconnect_warn)

            if connection is not None:
                self.hass.data[DATA_CONNECTIONS] -= 1
            self.hass.helpers.dispatcher.async_dispatcher_send(
                SIGNAL_WEBSOCKET_DISCONNECTED)

        return wsock
