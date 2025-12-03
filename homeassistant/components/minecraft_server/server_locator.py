"""Locate minecraft servers to use when adding new devices."""

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Coroutine

from netifaces import InterfaceType, ifaddresses, interfaces
from netifaces.defs import Address

from .api import JavaServer


class ServerLocator(ABC):
    """Class encapsulating functionality related to locating servers.

    This is done usually through scanning the local network for running servers.
    """

    @abstractmethod
    async def find_servers(self) -> list[str]:
        """Returns a list of servers."""


class MockServerLocator(ServerLocator):
    """Mock version of the ServerLocator.

    Includes function should_return to specify if a result should be returned.
    """

    def __init__(self) -> None:
        """Init function for the class."""
        self._should_return = True

    def should_return(self, should_return: bool) -> None:
        """Specify whether the mock should return a value, or not."""
        self._should_return = should_return

    async def find_servers(self) -> list[str]:
        """Tries to locate servers."""
        if self._should_return:
            return ["127.0.0.1:25565"]
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
    """Version of ServerLocator meant to find servers on the local network."""

    async def find_servers(self) -> list[str]:
        """Returns a list of servers."""
        return await self._find_minecraft_servers_async()

    async def _find_minecraft_servers_async(self) -> list[str]:
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
