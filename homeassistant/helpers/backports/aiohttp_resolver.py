"""Backport of aiohttp's AsyncResolver for Home Assistant.

This is a backport of the AsyncResolver class from aiohttp 3.10.

Before aiohttp 3.10, on system with IPv6 support, AsyncResolver would not fallback
to providing A records when AAAA records were not available.

Additionally, unlike the ThreadedResolver, AsyncResolver
did not handle link-local addresses correctly.
"""

from __future__ import annotations

import asyncio
import socket
import sys
from typing import Any, TypedDict

import aiodns
from aiohttp.abc import AbstractResolver

# This is a backport of https://github.com/aio-libs/aiohttp/pull/8270
# This can be removed once aiohttp 3.10 is the minimum supported version.

_NUMERIC_SOCKET_FLAGS = socket.AI_NUMERICHOST | socket.AI_NUMERICSERV
_SUPPORTS_SCOPE_ID = sys.version_info >= (3, 9, 0)


class ResolveResult(TypedDict):
    """Resolve result.

    This is the result returned from an AbstractResolver's
    resolve method.

    :param hostname: The hostname that was provided.
    :param host: The IP address that was resolved.
    :param port: The port that was resolved.
    :param family: The address family that was resolved.
    :param proto: The protocol that was resolved.
    :param flags: The flags that were resolved.
    """

    hostname: str
    host: str
    port: int
    family: int
    proto: int
    flags: int


class AsyncResolver(AbstractResolver):
    """Use the `aiodns` package to make asynchronous DNS lookups."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the resolver."""
        if aiodns is None:
            raise RuntimeError("Resolver requires aiodns library")

        self._loop = asyncio.get_running_loop()
        self._resolver = aiodns.DNSResolver(*args, loop=self._loop, **kwargs)  # type: ignore[misc]

    async def resolve(  # type: ignore[override]
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[ResolveResult]:
        """Resolve a host name to an IP address."""
        try:
            resp = await self._resolver.getaddrinfo(
                host,
                port=port,
                type=socket.SOCK_STREAM,
                family=family,  # type: ignore[arg-type]
                flags=socket.AI_ADDRCONFIG,
            )
        except aiodns.error.DNSError as exc:
            msg = exc.args[1] if len(exc.args) >= 1 else "DNS lookup failed"
            raise OSError(msg) from exc
        hosts: list[ResolveResult] = []
        for node in resp.nodes:
            address: tuple[bytes, int] | tuple[bytes, int, int, int] = node.addr
            family = node.family
            if family == socket.AF_INET6:
                if len(address) > 3 and address[3] and _SUPPORTS_SCOPE_ID:
                    # This is essential for link-local IPv6 addresses.
                    # LL IPv6 is a VERY rare case. Strictly speaking, we should use
                    # getnameinfo() unconditionally, but performance makes sense.
                    result = await self._resolver.getnameinfo(
                        (address[0].decode("ascii"), *address[1:]),
                        _NUMERIC_SOCKET_FLAGS,
                    )
                    resolved_host = result.node
                else:
                    resolved_host = address[0].decode("ascii")
                    port = address[1]
            else:  # IPv4
                assert family == socket.AF_INET
                resolved_host = address[0].decode("ascii")
                port = address[1]
            hosts.append(
                ResolveResult(
                    hostname=host,
                    host=resolved_host,
                    port=port,
                    family=family,
                    proto=0,
                    flags=_NUMERIC_SOCKET_FLAGS,
                )
            )

        if not hosts:
            raise OSError("DNS lookup failed")

        return hosts

    async def close(self) -> None:
        """Close the resolver."""
        self._resolver.cancel()
