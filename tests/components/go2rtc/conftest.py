"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from awesomeversion import AwesomeVersion
from go2rtc_client.rest import _StreamClient, _WebRTCClient
import pytest

from homeassistant.components.go2rtc.const import RECOMMENDED_VERSION
from homeassistant.components.go2rtc.server import Server

GO2RTC_PATH = "homeassistant.components.go2rtc"


@pytest.fixture
def rest_client() -> Generator[AsyncMock]:
    """Mock a go2rtc rest client."""
    with (
        patch(
            "homeassistant.components.go2rtc.Go2RtcRestClient",
        ) as mock_client,
        patch("homeassistant.components.go2rtc.server.Go2RtcRestClient", mock_client),
    ):
        client = mock_client.return_value
        client.streams = streams = Mock(spec_set=_StreamClient)
        streams.list.return_value = {}
        client.validate_server_version = AsyncMock(
            return_value=AwesomeVersion(RECOMMENDED_VERSION)
        )
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
def server_stdout() -> list[str]:
    """Server stdout lines."""
    return [
        "09:00:03.466 INF go2rtc platform=linux/amd64 revision=780f378 version=1.9.5",
        "09:00:03.466 INF config path=/tmp/go2rtc.yaml",
        "09:00:03.467 INF [rtsp] listen addr=:8554",
        "09:00:03.467 INF [api] listen addr=127.0.0.1:1984",
        "09:00:03.467 INF [webrtc] listen addr=:8555/tcp",
    ]


@pytest.fixture
def mock_create_subprocess(server_stdout: list[str]) -> Generator[AsyncMock]:
    """Mock create_subprocess_exec."""
    with patch(f"{GO2RTC_PATH}.server.asyncio.create_subprocess_exec") as mock_subproc:
        subproc = AsyncMock()
        subproc.terminate = Mock()
        subproc.kill = Mock()
        subproc.returncode = None
        # Simulate process output
        subproc.stdout.__aiter__.return_value = iter(
            [f"{entry}\n".encode() for entry in server_stdout]
        )
        mock_subproc.return_value = subproc
        yield mock_subproc


@pytest.fixture
def server_start(mock_create_subprocess: AsyncMock) -> Generator[AsyncMock]:
    """Mock start of a go2rtc server."""
    with patch(
        f"{GO2RTC_PATH}.server.Server.start", wraps=Server.start, autospec=True
    ) as mock_server_start:
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
def server(server_start: AsyncMock, server_stop: AsyncMock) -> Generator[AsyncMock]:
    """Mock a go2rtc server."""
    with patch(f"{GO2RTC_PATH}.Server", wraps=Server) as mock_server:
        yield mock_server
