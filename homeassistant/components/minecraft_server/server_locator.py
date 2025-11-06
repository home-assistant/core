"""Locate minecraft servers to use when adding new devices."""

from abc import ABC, abstractmethod
from typing import Any

from netifaces import ifaddresses, interfaces  # pylint: disable=no-name-in-module
from nmap import PortScanner


class ServerLocator(ABC):
    """Class encapsulating functionality related to locating servers.

    This is done usually through scanning the local network for running servers.
    """

    @abstractmethod
    def find_servers(self) -> list[str]:
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

    def find_servers(self) -> list[str]:
        """Tries to locate servers."""
        if self._should_return:
            return ["127.0.0.1:25565"]
        return []


class LocalServerLocator(ServerLocator):
    """Version of ServerLocator meant to find servers on the local network."""

    def find_servers(self) -> list[str]:
        """Returns a list of servers."""
        local_networks = self._find_local_networks()
        scanner = PortScanner()
        local_servers = []
        for net in local_networks:
            scanner.scan(
                self._convert_to_subnet(net.get("addr").get("addr")),
                "25565,19132,19133",
            )
            local_servers += self._find_minecraft_servers(scanner)
        return local_servers

    def _convert_to_subnet(self, ip: str) -> str:
        return ".".join(ip.split(".")[:3]) + ".0/24"

    def _find_minecraft_servers(self, scanner: PortScanner) -> list[str]:
        return list(
            filter(
                lambda host: scanner[host]["tcp"][25565]["state"] == "open",
                scanner.all_hosts(),
            )
        )

    def _find_local_networks(self) -> Any:
        ifaces = interfaces()
        local_networks = []
        for interface in ifaces:
            address = ifaddresses(interface).get(2)
            if address is None:
                continue
            ip = address[0].get("addr")
            if ip[:7] == "192.168" or ip[:3] == "10." or ip[:4] == "172.":
                local_networks.append({"int": interface, "addr": address[0]})
        return local_networks
