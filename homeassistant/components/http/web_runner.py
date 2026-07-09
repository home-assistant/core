"""HomeAssistant specific aiohttp Site."""

import asyncio
import errno
import os
from pathlib import Path
import socket
import sys
from typing import override

from aiohttp import web


def create_server_sockets(hosts: list[str], port: int) -> list[socket.socket]:
    """Create and bind the listening sockets for the given hosts and port.

    Mirrors the bind behavior of ``loop.create_server()`` (multiple hosts,
    ``SO_REUSEADDR``, ``IPV6_V6ONLY``, skipping unavailable address families)
    but only binds, so an unusable configuration surfaces before it is
    applied. Serving starts later, when the sockets are handed to aiohttp.

    Performs blocking name resolution and is intended to be run in an
    executor. Raises OSError (including ``socket.gaierror``) if the
    configuration cannot be bound.
    """
    # Resolve all hosts up front so an unresolvable one fails the whole
    # configuration before any socket is bound. Dict keys de-duplicate
    # while keeping resolution order.
    addr_infos = {
        info: None
        for host in hosts
        for info in socket.getaddrinfo(
            host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
        )
    }
    reuse_address = os.name == "posix" and sys.platform != "cygwin"

    sockets: list[socket.socket] = []
    try:
        for family, socktype, proto, _canonname, address in addr_infos:
            try:
                sock = socket.socket(family, socktype, proto)
            except OSError:
                # Address family not supported on this system
                continue
            sockets.append(sock)
            if reuse_address:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Disable IPv4/IPv6 dual stack support (enabled by default on
            # Linux) which makes a single socket listen on both address
            # families.
            if family == socket.AF_INET6 and hasattr(socket, "IPPROTO_IPV6"):
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            try:
                sock.bind(address)
            except OSError as err:
                if err.errno == errno.EADDRNOTAVAIL:
                    # Assume the address family is not enabled (bpo-30945)
                    sockets.pop()
                    sock.close()
                    continue
                raise OSError(
                    err.errno,
                    f"error while attempting to bind on address {address!r}: "
                    f"{(err.strerror or str(err)).lower()}",
                ) from None
    except BaseException:
        for sock in sockets:
            sock.close()
        raise
    if not sockets:
        raise OSError(
            f"could not bind on any address out of {[info[4] for info in addr_infos]!r}"
        )
    return sockets


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
