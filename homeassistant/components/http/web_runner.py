"""HomeAssistant specific aiohttp Site."""

from __future__ import annotations

import asyncio
from pathlib import Path
import socket
from ssl import SSLContext

from aiohttp import web
from yarl import URL


class HomeAssistantTCPSite(web.BaseSite):
    """HomeAssistant specific aiohttp Site.

    Vanilla TCPSite accepts only str as host. However, the underlying asyncio's
    create_server() implementation does take a list of strings to bind to multiple
    host IP's. To support multiple server_host entries (e.g. to enable dual-stack
    explicitly), we would like to pass an array of strings. Bring our own
    implementation inspired by TCPSite.

    Custom TCPSite can be dropped when https://github.com/aio-libs/aiohttp/pull/4894
    is merged.
    """

    __slots__ = ("_host", "_hosturl", "_port", "_reuse_address", "_reuse_port")

    def __init__(
        self,
        runner: web.BaseRunner,
        host: str | list[str] | None,
        port: int,
        *,
        ssl_context: SSLContext | None = None,
        backlog: int = 128,
        reuse_address: bool | None = None,
        reuse_port: bool | None = None,
    ) -> None:
        """Initialize HomeAssistantTCPSite."""
        super().__init__(
            runner,
            ssl_context=ssl_context,
            backlog=backlog,
        )
        self._host = host
        self._port = port
        self._reuse_address = reuse_address
        self._reuse_port = reuse_port

    @property
    def name(self) -> str:
        """Return server URL."""
        scheme = "https" if self._ssl_context else "http"
        host = self._host[0] if isinstance(self._host, list) else "0.0.0.0"
        return str(URL.build(scheme=scheme, host=host, port=self._port))

    async def start(self) -> None:
        """Start server."""
        await super().start()
        loop = asyncio.get_running_loop()
        server = self._runner.server
        assert server is not None
        self._server = await loop.create_server(
            server,
            self._host,
            self._port,
            ssl=self._ssl_context,
            backlog=self._backlog,
            reuse_address=self._reuse_address,
            reuse_port=self._reuse_port,
        )


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
