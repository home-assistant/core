"""Emulation of Legrand RFLC LC7001."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
import contextlib
from typing import Final
from unittest.mock import patch

from homeassistant.components.legrand_rflc.const import DOMAIN
from homeassistant.const import CONF_AUTHENTICATION, CONF_HOST

from tests.common import MockConfigEntry


async def _session(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    messages: Sequence[bytes],
    write=True,
    prefix: str = "",
):
    # alternate between writing and reading expected lines
    for message in messages:
        if write:
            writer.write(message)
            await writer.drain()
        else:
            assert message == await reader.readexactly(len(message))
        write ^= True
    writer.close()
    await writer.wait_closed()


class Server:
    """Emulated LC7001 Server for serving a matching config entry."""

    HOST: Final = "127.0.0.1"  # do not depend on "localhost" name resolution
    ADDRESS: Final = "127.0.0.1"
    MAC = "0026EC000000"

    # https://static.developer.legrand.com/files/2021/03/LC7001-AU7000-Security-Addendum-RevB.pdf
    # 7.3
    PASSWORD: Final = "MyNewPassword234"
    AUTHENTICATION: Final = "601CEF6593132D073B100830863E4DE2"
    AUTHENTICATION_OLD: Final = "D41D8CD98F00B204E9800998ECF8427E"

    SECURITY_NON_COMPLIANT: Final = b'{"MAC":"0026EC000000"}{"ID":0,"Service":"ping","CurrentTime":1626452977,"PingSeq":1,"Status":"Success"}\x00'

    SECURITY_HELLO_AUTHENTICATION_OK: Final = [
        b"Hello V1 \x009158E315149BEF9F2179D79C58F0F422 0026EC000000",
        b"3437872f1912fe9fb06ddf50eb5bf535",
        b"[OK]\n\r\n\x00",
    ]
    SECURITY_HELLO_AUTHENTICATION_INVALID: Final = [
        b"Hello V1 \x009158E315149BEF9F2179D79C58F0F422 0026EC000000",
        b"3437872f1912fe9fb06ddf50eb5bf535",
        b"[INVALID]\x00",
    ]
    SECURITY_HELLO_AUTHENTICATION_INVALID_MAC: Final = [
        b"Hello V1 \x009158E315149BEF9F2179D79C58F0F422 0026ECFFFFFF",
        b"3437872f1912fe9fb06ddf50eb5bf535",
        b"[OK]\x00",
    ]

    class _Relay(asyncio.StreamWriter):
        class _Transport(asyncio.WriteTransport):
            def __init__(self, reader: asyncio.StreamReader):
                super().__init__()
                self._reader = reader
                self._is_closing = False

            def write(self, data):
                self._reader.feed_data(data)

            def write_eof(self):
                self._reader.feed_eof()  # will raise EOFError when read

            def close(self):
                self.write_eof()
                self._is_closing = True

            def is_closing(self):
                return self._is_closing

        class _Protocol(asyncio.Protocol):
            async def _get_close_waiter(self, writer: asyncio.StreamWriter):
                pass

            async def _drain_helper(self):
                pass

        def __init__(self):
            reader = asyncio.StreamReader()
            super().__init__(
                self._Transport(reader),
                self._Protocol(),
                reader,
                asyncio.get_running_loop(),
            )

    def __init__(self, hass, sessions: Sequence[Sequence[str]]):
        """Each session is an alternating sequence of messages to write and messages we expect to read."""
        self._hass = hass
        self._sessions = sessions
        self._queue = asyncio.Queue(1)

    async def _accept(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        await self._queue.get()
        self._relays = [self._Relay(), self._Relay()]
        self._queue.task_done()
        return (self._relays[1]._reader, self._relays[0])

    async def _connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if self._queue is None:
            raise asyncio.CancelledError from ConnectionError
        await self._queue.put(None)
        await self._queue.join()
        return (self._relays[0]._reader, self._relays[1])

    async def _loop(self):
        for messages in self._sessions:
            await _session(*await self._accept(), messages)
        self._queue = None

    class Context(contextlib.AbstractAsyncContextManager):
        """Manage a Context for the lifetime of a Server."""

        def __init__(self, server: Server):
            """Initialize the context of a Server."""
            self._server = server
            self._patcher = patch("lc7001.aio._ConnectionContext")

        async def __aenter__(self):
            """Enter the context of a Server."""
            self._task = asyncio.create_task(self._server._loop())
            mock = self._patcher.start()

            async def _aenter(
                instance,
            ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
                return await self._server._connect()

            instance = mock.return_value
            instance.__aenter__ = _aenter

        async def __aexit__(self, et, ev, tb):
            """Exit the context of a Server."""
            await self._server._hass.async_block_till_done()
            self._patcher.stop()
            await self._task

    @classmethod
    def mock_entry(cls, hass):
        """Mock a ConfigEntry for a Server."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=cls.MAC.lower(),
            data={
                CONF_AUTHENTICATION: cls.AUTHENTICATION,
                CONF_HOST: cls.HOST,
            },
        )
        entry.add_to_hass(hass)
        return entry.entry_id

    async def start(self):
        """Manage a Context for the lifetime of a mocked ConfigEntry."""
        async with self.Context(self):
            self._hass.async_create_task(
                self._hass.config_entries.async_setup(self.mock_entry(self._hass))
            )
