"""HomeAssistant specific aiohttp Site."""

import asyncio
from pathlib import Path
import socket
from typing import override

from aiohttp import web


class HomeAssistantUnixSite(web.BaseSite):
    """HomeAssistant specific aiohttp UnixSite.

    Listens on a Unix socket for local inter-process communication,
    used for Supervisor to Core communication.
    """

    __slots__ = ("_path",)

    def __init__(
        self,
        runner: web.BaseRunner,
        path: Path,
        *,
        backlog: int = 128,
    ) -> None:
        """Initialize HomeAssistantUnixSite."""
        super().__init__(
            runner,
            backlog=backlog,
        )
        self._path = path

    @property
    @override
    def name(self) -> str:
        """Return server URL."""
        return f"http://unix:{self._path}:"

    def _create_unix_socket(self) -> socket.socket:
        """Create and bind a Unix domain socket.

        Performs blocking filesystem I/O (mkdir, unlink, chmod) and is
        intended to be run in an executor. Permissions are set after bind
        but before the socket is handed to the event loop, so no
        connections can arrive on an unrestricted socket.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.unlink(missing_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self._path))
            self._path.chmod(0o600)
        except OSError:
            sock.close()
            raise
        return sock

    @override
    async def start(self) -> None:
        """Start server."""
        await super().start()
        loop = asyncio.get_running_loop()
        sock = await loop.run_in_executor(None, self._create_unix_socket)
        server = self._runner.server
        assert server is not None
        self._server = await loop.create_unix_server(
            server, sock=sock, backlog=self._backlog
        )
