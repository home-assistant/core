"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from go2rtc_client.client import _StreamClient, _WebRTCClient
import pytest

from homeassistant.components.go2rtc.server import Server


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
def mock_server() -> Generator[AsyncMock]:
    """Mock a go2rtc server."""
    with patch(
        "homeassistant.components.go2rtc.Server", spec_set=Server
    ) as mock_server:
        yield mock_server
