"""Implement the Lutron Integration Protocol."""

import asyncio
import logging
import socket
import time

__version__ = "1.1.7"

from collections.abc import Callable

__all__ = ["LIPAction", "LIPGroupState", "LIPLedState"]

from .data import (
    LIPAction,
    LIPGroupState,
    LIPLedState,
    LIPMessage,
    LIPMode,
    LIPOperation,
)
from .exceptions import LIPConnectionStateError, LIPProtocolError
from .protocol import (
    CONNECT_TIMEOUT,
    LIP_KEEP_ALIVE,
    LIP_KEEP_ALIVE_INTERVAL,
    LIP_PASSWORD,
    LIP_PORT,
    LIP_PROTOCOL_GENERIC_NET,
    LIP_PROTOCOL_GNET,
    LIP_PROTOCOL_LOGIN,
    LIP_PROTOCOL_PASSWORD,
    LIP_PROTOCOL_QNET,
    LIP_READ_TIMEOUT,
    LIP_USERNAME,
    SOCKET_TIMEOUT,
    LIPConnectionState,
    LIPControllerType,
    LIPParser,
    LIPSocket,
)

_LOGGER = logging.getLogger(__name__)


class LIP:
    """Async class to speak LIP."""

    def __init__(self):
        """Create the LIP class."""
        self.connection_state = LIPConnectionState.NOT_CONNECTED
        self._controller_type = None
        self._lip = None
        self._host = None
        self._parser = LIPParser()
        self._read_connect_lock = asyncio.Lock()
        self._disconnect_event = asyncio.Event()
        self._reconnecting_event = asyncio.Event()
        self._callback = None  # Only one callback, the coordinator
        self._keep_alive_reconnect_task = None
        self._last_keep_alive_response = None
        self._keep_alive_task = None
        self.loop = None

    async def async_connect(self, server_addr):
        """Connect to the bridge via LIP."""
        self.loop = asyncio.get_event_loop()

        if self.connection_state != LIPConnectionState.NOT_CONNECTED:
            raise LIPConnectionStateError

        self._disconnect_event.clear()

        try:
            await self._async_connect(server_addr)
        except TimeoutError:
            _LOGGER.debug("Timed out while trying to connect to %s", server_addr)
            self.connection_state = LIPConnectionState.NOT_CONNECTED
            raise

        # set the correct monitoring
        await self.action(LIPMode.MONITORING, 12, 2)  # disable prompt state
        await self.action(
            LIPMode.MONITORING, 255, 2
        )  # disable everything (not reply state 11, not prompt 12)
        await self.action(LIPMode.MONITORING, 3, 1)  # Button
        await self.action(LIPMode.MONITORING, 4, 1)  # Led
        await self.action(LIPMode.MONITORING, 5, 1)  # Zone
        await self.action(LIPMode.MONITORING, 6, 1)  # Occupancy
        await self.action(LIPMode.MONITORING, 8, 1)  # Scene
        await self.action(LIPMode.MONITORING, 10, 1)  # SysVar

    async def _async_connect(self, server_addr):
        """Make the connection."""
        _LOGGER.debug("Connecting to %s", server_addr)
        self.connection_state = LIPConnectionState.CONNECTING
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                server_addr,
                LIP_PORT,
                family=socket.AF_INET,
            ),
            timeout=CONNECT_TIMEOUT,
        )
        self._lip = LIPSocket(reader, writer)
        _verify_expected_response(
            await self._lip.async_readuntil(" "), LIP_PROTOCOL_LOGIN
        )
        await self._lip.async_write_command(LIP_USERNAME)
        _verify_expected_response(
            await self._lip.async_readuntil(" "), LIP_PROTOCOL_PASSWORD
        )
        await self._lip.async_write_command(LIP_PASSWORD)

        controller_type = await self._lip.async_readuntil(" ")

        _verify_expected_response(controller_type, LIP_PROTOCOL_GENERIC_NET)

        if LIP_PROTOCOL_QNET in controller_type:
            self._controller_type = LIPControllerType.HOMEWORKS
        elif LIP_PROTOCOL_GNET in controller_type:
            self._controller_type = LIPControllerType.RADIORA2
        else:
            self._controller_type = LIPControllerType.UNKNOWN
            _LOGGER.warning("Unknown controller type: %s", controller_type)

        self.connection_state = LIPConnectionState.CONNECTED
        self._host = server_addr
        self._reconnecting_event.clear()
        _LOGGER.debug("Connected to %s", server_addr)

    async def _async_disconnected(self):
        """Reconnect after disconnected."""
        if self._reconnecting_event.is_set():
            return

        if self._lip:
            self._lip.close()
            self._lip = None

        self._reconnecting_event.set()
        async with self._read_connect_lock:
            self.connection_state = LIPConnectionState.NOT_CONNECTED
            while not self._disconnect_event.is_set():
                try:
                    await self._async_connect(self._host)
                except (TimeoutError, OSError):
                    _LOGGER.debug(
                        "Timed out while trying to reconnect to %s", self._host
                    )
                else:
                    self._keepalive_watchdog()
                    return

    async def async_stop(self):
        """Disconnect from the bridge."""
        self._disconnect_event.set()
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            self._keep_alive_task = None
        self._lip.close()

    async def _async_keep_alive_or_reconnect(self):
        """Keep alive or reconnect."""
        connection_error = False
        try:
            await self._lip.async_write_command(LIP_KEEP_ALIVE)
        except (TimeoutError, ConnectionResetError) as ex:
            _LOGGER.debug("Lutron bridge disconnected: %s", ex)
            connection_error = True

        if connection_error or self._last_keep_alive_response < time.time() - (
            LIP_KEEP_ALIVE_INTERVAL + SOCKET_TIMEOUT
        ):
            _LOGGER.debug("Lutron bridge keep alive timeout, reconnecting")
            await self._async_disconnected()
            self._last_keep_alive_response = time.time()

    def _keepalive_watchdog(self):
        """Send keepalives."""
        if (
            self._disconnect_event.is_set()
            or self.connection_state != LIPConnectionState.CONNECTED
        ):
            return

        self._keep_alive_reconnect_task = asyncio.create_task(
            self._async_keep_alive_or_reconnect()
        )

        self._keep_alive_task = self.loop.call_later(
            LIP_KEEP_ALIVE_INTERVAL, self._keepalive_watchdog
        )

    async def async_run(self):
        """Start interacting with the bridge."""
        if self.connection_state != LIPConnectionState.CONNECTED:
            raise LIPConnectionStateError

        self._last_keep_alive_response = time.time()
        self._keepalive_watchdog()

        while not self._disconnect_event.is_set():
            await self._async_run_once()

    async def _async_run_once(self):
        """Process one message or event."""
        async with self._read_connect_lock:
            read_task = asyncio.create_task(self._lip.async_readline())
            disconnect_task = asyncio.create_task(self._disconnect_event.wait())
            reconnecting_task = asyncio.create_task(self._reconnecting_event.wait())

            _, pending = await asyncio.wait(
                (
                    read_task,
                    disconnect_task,
                    reconnecting_task,
                ),
                timeout=LIP_READ_TIMEOUT,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

        if self._disconnect_event.is_set():
            _LOGGER.debug("Stopping run because of disconnect_event")
            return

        if self._reconnecting_event.is_set():
            _LOGGER.debug("Stopping run because of reconnecting_event")
            return

        try:
            self._process_message(read_task.result())
        except TimeoutError:
            return
        except (asyncio.InvalidStateError, BrokenPipeError) as ex:
            _LOGGER.debug("Error processing message", exc_info=ex)
            return

    def _process_message(self, response):
        """Process a lip message. This is processing only response (i.e. ~") events."""

        message = self._parser.parse(response)

        if message:
            if message.mode == LIPMode.KEEPALIVE:
                self._last_keep_alive_response = self._parser.last_keepalive
            elif message.mode == LIPMode.ERROR:
                _LOGGER.error("Protocol Error: %s", response)
            elif message.mode != LIPMode.UNKNOWN:
                try:
                    if self._callback:
                        self._callback(message)
                except ValueError:
                    _LOGGER.warning("Error dispatching message: %s", response)
            else:
                _LOGGER.debug("Unknown lutron message: %s", response)

    async def query(self, mode, *args):
        """Query the bridge."""
        await self._async_send_command(LIPOperation.QUERY, mode, *args)

    async def action(self, mode, *args):
        """Do an action on the bridge."""
        await self._async_send_command(LIPOperation.EXECUTE, mode, *args)

    def set_callback(self, callback: Callable[[LIPMessage], None]) -> None:
        """Set the callback for LIP messages."""
        self._callback = callback

    async def _async_send_command(self, protocol_header, mode, *cmd):
        """Send a command."""
        if self.connection_state != LIPConnectionState.CONNECTED:
            raise LIPConnectionStateError

        assert isinstance(mode, LIPMode)

        request = ",".join([mode.name, *[str(key) for key in cmd]])
        _LOGGER.debug("Outgoing message:%s-%s", protocol_header, request)
        await self._lip.async_write_command(f"{protocol_header}{request}")


def _verify_expected_response(received, expected):
    if expected not in received:
        raise LIPProtocolError(received, expected)
