"""SamsungTV Encrypted."""
import asyncio
import contextlib
import logging
import time
from types import TracebackType
from typing import List, Optional

import aiohttp
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed

from samsungtvws.exceptions import ConnectionFailure
from .command import SamsungTVEncryptedCommand
from .session import SamsungTVEncryptedSession

LOGGER = logging.getLogger(__name__)


class SendRemoteKey:
    @staticmethod
    def click(key: str) -> SamsungTVEncryptedCommand:
        return SamsungTVEncryptedCommand(
            "POST",
            {
                "plugin": "RemoteControl",
                "param1": "uuid:12345",
                "param2": "Click",
                "param3": key,
                "param4": False,
                "api": "SendRemoteKey",
                "version": "1.000",
            },
        )


class SamsungTVEncryptedWSAsyncRemote:
    REST_URL_FORMAT = "http://{host}:{port}/{route}"
    URL_FORMAT = "ws://{host}:{port}/socket.io/1/websocket/{app}"

    _connection: Optional[WebSocketClientProtocol]
    _recv_loop: Optional["asyncio.Task[None]"]

    def __init__(
        self,
        host: str,
        *,
        web_session: aiohttp.ClientSession,
        token: str,
        session_id: str,
        port: int = 8000,
        timeout: Optional[float] = None,
        key_press_delay: float = 1,
    ) -> None:
        self._host = host
        self._key_press_delay = key_press_delay
        self._port = port
        self._session: Optional[SamsungTVEncryptedSession] = None
        if token and session_id:
            self._session = SamsungTVEncryptedSession(token, session_id)

        self._timeout = None if timeout == 0 else timeout
        self._web_session = web_session
        self._connection = None
        self._recv_loop = None

    async def __aenter__(self) -> "SamsungTVEncryptedWSAsyncRemote":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    def _format_websocket_url(self, app: str) -> str:
        params = {
            "host": self._host,
            "port": self._port,
            "app": app,
        }

        return self.URL_FORMAT.format(**params)

    def _format_rest_url(self, route: str = "") -> str:
        params = {
            "host": self._host,
            "port": self._port,
            "route": route,
        }

        return self.REST_URL_FORMAT.format(**params)

    async def _open(self) -> None:
        if self._connection:
            # someone else already created a new connection
            return

        millis = int(round(time.time() * 1000))
        step4_url = self._format_rest_url(f"socket.io/1/?t={millis}")
        LOGGER.debug("Tx: GET %s", step4_url)

        async with self._web_session.get(step4_url) as response:
            LOGGER.debug("Rx: %s", await response.text())
            step4_response = await response.text()

        url = self._format_websocket_url(step4_response.split(":")[0])
        LOGGER.debug("WS url %s", url)

        connection = await connect(url, open_timeout=self._timeout)
        await connection.send("1::/com.samsung.companion")

        self._connection = connection

    async def start_listening(self) -> None:
        """Open, and start listening."""
        if self._connection:
            raise ConnectionFailure("Connection already exists")

        await self._open()
        assert self._connection

        self._recv_loop = asyncio.ensure_future(
            self._do_start_listening(self._connection)
        )

    @staticmethod
    async def _do_start_listening(
        connection: WebSocketClientProtocol,
    ) -> None:
        """Do start listening."""
        with contextlib.suppress(ConnectionClosed):
            while True:
                data = await connection.recv()
                LOGGER.debug("SamsungTVEncryptedWS websocket event: %s", data)

    async def send_command(
        self,
        command: SamsungTVEncryptedCommand,
        key_press_delay: Optional[float] = None,
    ) -> None:
        await self.send_commands([command], key_press_delay)

    async def send_commands(
        self,
        commands: List[SamsungTVEncryptedCommand],
        key_press_delay: Optional[float] = None,
    ) -> None:
        assert self._session
        if self._connection is None:
            await self._open()
            assert self._connection

        delay = self._key_press_delay if key_press_delay is None else key_press_delay
        for command in commands:
            await self._send_command(self._connection, command, self._session, delay)

    @staticmethod
    async def _send_command(
        connection: WebSocketClientProtocol,
        command: SamsungTVEncryptedCommand,
        session: SamsungTVEncryptedSession,
        delay: float,
    ) -> None:
        LOGGER.debug("SamsungTVEncryptedWS websocket command: %s", command.as_dict())
        payload = session.encrypt_command(command)

        LOGGER.debug("SamsungTVEncryptedWS websocket command (encrypted): %s", payload)
        await connection.send(payload)

        await asyncio.sleep(delay)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            if self._recv_loop:
                await self._recv_loop

        self._connection = None
        LOGGER.debug("Connection closed")

    def is_alive(self) -> bool:
        return self._connection is not None and not self._connection.closed
