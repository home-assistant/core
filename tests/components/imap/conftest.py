"""Fixtures for imap tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioimaplib import AUTH, LOGOUT, NONAUTH, SELECTED, STARTED, Response
import pytest

from .const import EMPTY_SEARCH_RESPONSE, TEST_FETCH_RESPONSE


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
def imap_login_state() -> Generator[str, None]:
    """Fixture to set the imap state after login."""
    return AUTH


@pytest.fixture
def imap_select_state() -> Generator[str, None]:
    """Fixture to set the imap capabilities."""
    return SELECTED


@pytest.fixture
def imap_search() -> Generator[tuple[str, list[bytes]], None]:
    """Fixture to set the imap search response."""
    return EMPTY_SEARCH_RESPONSE


@pytest.fixture
def imap_fetch() -> Generator[tuple[str, list[bytes | bytearray]], None]:
    """Fixture to set the imap fetch response."""
    return TEST_FETCH_RESPONSE


@pytest.fixture
def imap_pending_idle() -> Generator[bool, None]:
    """Fixture to set the imap pending idle feature."""
    return True


@pytest.fixture
async def mock_imap_protocol(
    imap_search: tuple[str, list[bytes]],
    imap_fetch: tuple[str, list[bytes | bytearray]],
    imap_capabilities: set[str],
    imap_pending_idle: bool,
    imap_login_state: str,
    imap_select_state: str,
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
            self.wait_server_push = AsyncMock()
            self.noop = AsyncMock()
            self.has_pending_idle = MagicMock(return_value=imap_pending_idle)
            self.idle_start = AsyncMock()
            self.idle_done = MagicMock()
            self.stop_wait_server_push = AsyncMock(return_value=True)
            self.protocol = self.IMAP4ClientProtocolMock()

        def has_capability(self, capability: str) -> bool:
            """Check capability."""
            return capability in self.protocol.capabilities

        async def login(self, user: str, password: str) -> Response:
            """Mock imap login."""
            self.protocol.state = imap_login_state
            if imap_login_state != AUTH:
                return Response("BAD", [])
            return Response("OK", [b"CAPABILITY IMAP4rev1 ...", b"Logged in"])

        async def close(self) -> Response:
            """Mock imap close the selected folder."""
            self.protocol.state = imap_login_state
            return Response("OK", [])

        async def logout(self) -> Response:
            """Mock imap logout."""
            self.protocol.state = LOGOUT
            return Response("OK", [])

        async def select(self, mailbox: str = "INBOX") -> Response:
            """Mock imap folder select."""
            self.protocol.state = imap_select_state
            if imap_login_state != SELECTED:
                return Response("BAD", [])
            return Response("OK", [])

        async def search(self, *criteria: str, charset: str = "utf-8") -> Response:
            """Mock imap search."""
            return Response(*imap_search)

        async def fetch(self, message_set: str, message_parts: str) -> Response:
            """Mock imap fetch."""
            return Response(*imap_fetch)

        async def wait_hello_from_server(self) -> None:
            """Mock wait for hello."""
            self.protocol.state = NONAUTH

    with patch(
        "homeassistant.components.imap.coordinator.IMAP4_SSL",
        side_effect=IMAP4ClientMock,
    ) as protocol:
        yield protocol
