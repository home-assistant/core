"""SamsungTV Encrypted."""
# flake8: noqa
# pylint: disable=[missing-class-docstring,missing-function-docstring]
from __future__ import annotations

import asyncio
import logging
import time
from types import TracebackType

import aiohttp
from samsungtvws.connection import SamsungTVWSBaseConnection
from websockets.client import WebSocketClientProtocol, connect

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


class SamsungTVEncryptedWSAsyncRemote(SamsungTVWSBaseConnection):
    connection: WebSocketClientProtocol | None
    _recv_loop: asyncio.Task[None] | None

    _URL_FORMAT = "ws://{host}:{port}/socket.io/1/websocket/{app}"
    _REST_URL_FORMAT = "http://{host}:{port}/{route}"

    def __init__(
        self,
        host: str,
        *,
        web_session: aiohttp.ClientSession,
        token: str,
        session_id: str,
        port: int = 8000,
        timeout: float | None = None,
        key_press_delay: float = 1,
        name: str = "SamsungTvRemote",
    ) -> None:
        super().__init__(
            host,
            endpoint="",
            token=token,
            port=port,
            timeout=timeout,
            key_press_delay=key_press_delay,
            name=name,
        )
        self._web_session = web_session
        self._session = SamsungTVEncryptedSession(token, session_id)

    async def __aenter__(self) -> SamsungTVEncryptedWSAsyncRemote:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    def _format_websocket_url(self, app: str) -> str:
        params = {
            "host": self.host,
            "port": self.port,
            "app": app,
        }

        return self._URL_FORMAT.format(**params)

    def _format_rest_url(self, route: str = "") -> str:
        params = {
            "host": self.host,
            "port": self.port,
            "route": route,
        }

        return self._REST_URL_FORMAT.format(**params)

    async def open(self) -> WebSocketClientProtocol:
        if self.connection:
            # someone else already created a new connection
            return self.connection

        millis = int(round(time.time() * 1000))
        step4_url = self._format_rest_url(f"socket.io/1/?t={millis}")
        LOGGER.debug("Tx: GET %s", step4_url)
        async with self._web_session.get(step4_url) as response:
            LOGGER.debug("Rx: %s", await response.text())
            step4_response = await response.text()

        url = self._format_websocket_url(step4_response.split(":")[0])

        LOGGER.debug("WS url %s", url)
        connection = await connect(url, open_timeout=self.timeout)
        await connection.send("1::/com.samsung.companion")

        self.connection = connection
        return connection

    async def send_command(
        self,
        command: SamsungTVEncryptedCommand,
        key_press_delay: float | None = None,
    ) -> None:
        await self.send_commands([command], key_press_delay)

    async def send_commands(
        self,
        commands: list[SamsungTVEncryptedCommand],
        key_press_delay: float | None = None,
    ) -> None:
        if self.connection is None:
            self.connection = await self.open()

        delay = self.key_press_delay if key_press_delay is None else key_press_delay

        for command in commands:
            await self._send_command(self.connection, command, self._session, delay)

    @staticmethod
    async def _send_command(
        connection: WebSocketClientProtocol,
        command: SamsungTVEncryptedCommand,
        session: SamsungTVEncryptedSession,
        delay: float,
    ) -> None:
        payload = session.encrypt_command(command)
        await connection.send(payload)

        await asyncio.sleep(delay)

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()
            if self._recv_loop:
                await self._recv_loop

        self.connection = None
        LOGGER.debug("Connection closed")

    def is_alive(self) -> bool:
        return self.connection is not None and not self.connection.closed
