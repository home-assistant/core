"""Fixtures for imap tests."""


from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioimaplib import AUTH, SELECTED, STARTED, Response
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.imap.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


def imap_capabilities() -> Generator[set[str], None]:
    """Fixture to set the imap capabilities."""
    return {"IDLE"}


@pytest.fixture
def imap_search() -> Generator[tuple[str, list[bytes]], None]:
    """Fixture to set the imap search response."""
    return ("OK", [b"", b"Search completed (0.0001 + 0.000 secs)."])


@pytest.fixture
def imap_pending_idle() -> Generator[bool, None]:
    """Fixture to set the imap pending idle feature."""
    return True


@pytest.fixture
async def mock_imap_protocol(
    imap_search: tuple[str, list[bytes]],
    imap_capabilities: set[str],
    imap_pending_idle: bool,
) -> Generator[MagicMock, None]:
    """Mock the aioimaplib IMAP protocol handler."""

    class IMAP4ClientMock:
        """Mock for IMAP4 client."""

        class IMAP4ClientProtocolMock:
            """Mock the IMAP4 client protocol."""

            state: str = STARTED

            @property
            def capabilities(self) -> set[str]:
                """Mock the capabilities."""
                return imap_capabilities

        def __init__(self, *args, **kwargs) -> None:
            self._state = STARTED
            self.wait_hello_from_server = AsyncMock()
            self.wait_server_push = AsyncMock()
            self.noop = AsyncMock()
            self.has_pending_idle = MagicMock(return_value=imap_pending_idle)
            self.idle_start = AsyncMock()
            self.idle_done = MagicMock()
            self.stop_wait_server_push = AsyncMock()
            self.close = AsyncMock()
            self.logout = AsyncMock()
            self.protocol = self.IMAP4ClientProtocolMock()

        def has_capability(self, capability: str) -> bool:
            """Check capability."""
            return capability in self.protocol.capabilities

        async def login(self, user: str, password: str) -> Response:
            """Mock the login."""
            self.protocol.state = AUTH
            return ("OK", [])

        async def select(self, mailbox: str = "INBOX") -> Response:
            """Mock the folder select."""
            self.protocol.state = SELECTED
            return ("OK", [])

        async def search(self, *criteria: str, charset: str = "utf-8") -> Response:
            """Mock the imap search."""
            return imap_search

    with patch(
        "homeassistant.components.imap.coordinator.IMAP4_SSL",
        side_effect=IMAP4ClientMock,
    ) as protocol:
        yield protocol
