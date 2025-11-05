"""Locate minecraft servers to use when adding new devices."""

from abc import ABC, abstractmethod


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
