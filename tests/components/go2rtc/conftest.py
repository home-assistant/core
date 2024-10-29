"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from go2rtc_client.rest import _StreamClient, _WebRTCClient
import pytest

from homeassistant.components.go2rtc.server import Server

GO2RTC_PATH = "homeassistant.components.go2rtc"


@pytest.fixture
def rest_client() -> Generator[AsyncMock]:
    """Mock a go2rtc rest client."""
    with (
        patch(
            "homeassistant.components.go2rtc.Go2RtcRestClient",
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.streams = Mock(spec_set=_StreamClient)
        client.webrtc = Mock(spec_set=_WebRTCClient)
        yield client


@pytest.fixture
def ws_client() -> Generator[Mock]:
    """Mock a go2rtc websocket client."""
    with patch(
        "homeassistant.components.go2rtc.Go2RtcWsClient", autospec=True
    ) as ws_client_mock:
        yield ws_client_mock.return_value


@pytest.fixture
def server_start() -> Generator[AsyncMock]:
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
def server_stop() -> Generator[AsyncMock]:
    """Mock stop of a go2rtc server."""
    with (
        patch(
            f"{GO2RTC_PATH}.server.Server.stop", wraps=Server.stop, autospec=True
        ) as mock_server_stop,
    ):
        yield mock_server_stop


@pytest.fixture
def server(server_start, server_stop) -> Generator[AsyncMock]:
    """Mock a go2rtc server."""
    with patch(f"{GO2RTC_PATH}.Server", wraps=Server) as mock_server:
        yield mock_server
