"""Locate minecraft servers to use when adding new devices.

This module defines a small set of classes for discovering Minecraft servers.
The discovery logic is kept separate from the config flow so that networking
code is isolated, easier to test, and easier to change later.
"""

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Coroutine

from netifaces import InterfaceType, ifaddresses, interfaces
from netifaces.defs import Address

from .api import JavaServer


class ServerLocator(ABC):
    """Interface for discovering Minecraft servers.

    The goal of this class is to separate server-discovery logic from the
    config flow. By using a shared interface, the integration can support
    multiple discovery methods (local scanning, mock data, etc.) without
    changing the rest of the code.
    """

    @abstractmethod
    async def find_servers(self) -> list[str]:
        """Returns a list of servers."""


class MockServerLocator(ServerLocator):
    """Mock version of the ServerLocator.

    Used mainly for testing. This locator does not scan the network but returns
    a preset result. The method should_return() controls whether find_servers()
    will return a mock server or an empty list.
    """

    def __init__(self) -> None:
        """Initialize the mock locator with a default return value."""
        self._should_return = True

    def should_return(self, should_return: bool) -> None:
        """Specify whether the mock should return a value, or not."""
        self._should_return = should_return

    async def find_servers(self) -> list[str]:
        """Return a mock server or an empty list based on the current setting."""
        if self._should_return:
            return ["127.0.0.1:25565"]
        return []


class CommonServerLocator(ServerLocator):
    """Locator that returns a list of well-known public servers.

    Useful for testing or providing example servers. This locator does not scan
    the network. The method should_return() controls whether find_servers()
    returns the preset list or an empty list.
    """

    def __init__(self) -> None:
        """Initialize the locator with a default return value."""
        self._should_return = True

    def should_return(self, should_return: bool) -> None:
        """Specify whether the mock should return a value, or not."""
        self._should_return = should_return

    async def find_servers(self) -> list[str]:
        """Return the preset server list or an empty list based on the setting."""
        if self._should_return:
            return [
                "mc.hypixel.net:25565",
                "org.mc-complex.com:25565",
                "join.insanitycraft.net:25565",
                "hub.opblocks.com:25565",
                "mcs.vanillarealms.com:25565",
                "org.mc-complex.com:25565",
            ]
        return []


def _get_all_ips(ip: str) -> list[str]:
    net = ".".join(ip.split(".")[:3])
    return [f"{net}.{x}" for x in range(1, 255)]


async def _ping_server(ip: str) -> None | str:
    try:
        await JavaServer(ip).async_status()  # pyright: ignore[reportUnknownMemberType]
    except Exception:  # noqa: BLE001
        return None
    return ip


class LocalServerLocator(ServerLocator):
    """Locator that scans the local network for Minecraft servers.

    Retrieves local network interfaces, generates IP addresses
    within each detected subnet, and tests each address to determine whether a
    Minecraft server is running there.
    """

    async def find_servers(self) -> list[str]:
        """Returns a list of servers."""
        return await self._find_minecraft_servers_async()

    async def _find_minecraft_servers_async(self) -> list[str]:
        """Scan all detected local subnets for Minecraft servers.

        Builds a list of IP addresses from all local networks and
        asynchronously tests each address. Only addresses that respond as a
        Minecraft server are returned.
        """
        tasks: list[Coroutine[None, None, str | None]] = []
        for _, address in await self._get_local_networks():
            for ip in _get_all_ips(address):
                tasks.extend([_ping_server(ip)])

        ip_results: list[str | None] = await asyncio.gather(*tasks)
        return [ip for ip in ip_results if ip is not None]

    async def _get_local_networks(
        self,
    ) -> list[tuple[str, Address]]:
        """Returns a list of local networks."""
        ifaces = interfaces()  # Returns a list of all networks
        local_networks: list[tuple[str, Address]] = []
        for interface in ifaces:
            address = ifaddresses(interface).get(InterfaceType.AF_INET)
            if address is None:
                continue
            ip: Address | None = address[0].get("addr")
            if ip is None:
                continue
            if ip.startswith(("192.168", "10.", "172.")):
                local_networks.append((interface, ip))
        return local_networks
