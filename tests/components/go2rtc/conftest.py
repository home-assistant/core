"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from go2rtc_client.client import _StreamClient, _WebRTCClient
import pytest

from homeassistant.components.go2rtc.server import Server

GO2RTC_PATH = "homeassistant.components.go2rtc"


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock a go2rtc client."""
    with (
        patch(
            "homeassistant.components.go2rtc.Go2RtcClient",
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.streams = Mock(spec_set=_StreamClient)
        client.webrtc = Mock(spec_set=_WebRTCClient)
        yield client


@pytest.fixture
def mock_server_start() -> Generator[AsyncMock]:
    """Mock start of a go2rtc server."""
    with (
        patch(f"{GO2RTC_PATH}.server.asyncio.create_subprocess_exec") as mock_subproc,
        patch(
            f"{GO2RTC_PATH}.server.Server.start", wraps=Server.start, autospec=True
        ) as mock_server_start,
    ):
        subproc = AsyncMock()
        subproc.terminate = Mock()
        mock_subproc.return_value = subproc
        yield mock_server_start


@pytest.fixture
def mock_server_stop() -> Generator[AsyncMock]:
    """Mock stop of a go2rtc server."""
    with (
        patch(
            f"{GO2RTC_PATH}.server.Server.stop", wraps=Server.stop, autospec=True
        ) as mock_server_stop,
    ):
        yield mock_server_stop


@pytest.fixture
def mock_server(mock_server_start, mock_server_stop) -> Generator[AsyncMock]:
    """Mock a go2rtc server."""
    with patch(f"{GO2RTC_PATH}.Server", wraps=Server) as mock_server:
        yield mock_server
