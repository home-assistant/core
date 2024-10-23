"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from go2rtc_client.rest import _StreamClient, _WebRTCClient
import pytest

from homeassistant.components.go2rtc.const import CONF_BINARY, DOMAIN
from homeassistant.components.go2rtc.server import Server
from homeassistant.const import CONF_URL

from . import HomeAssistant, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.go2rtc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def rest_client() -> Generator[AsyncMock]:
    """Mock a go2rtc rest client."""
    with (
        patch(
            "homeassistant.components.go2rtc.Go2RtcRestClient",
        ) as mock_client,
        patch(
            "homeassistant.components.go2rtc.config_flow.Go2RtcRestClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.streams = Mock(spec_set=_StreamClient)
        client.webrtc = Mock(spec_set=_WebRTCClient)
        yield client


@pytest.fixture
def server() -> Generator[AsyncMock]:
    """Mock a go2rtc server."""
    with patch(
        "homeassistant.components.go2rtc.Server", spec_set=Server
    ) as mock_server:
        yield mock_server


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_URL: "http://localhost:1984/", CONF_BINARY: "/usr/bin/go2rtc"},
    )


@pytest.fixture
def ws_client() -> Generator[Mock]:
    """Mock a go2rtc websocket client."""
    with patch(
        "homeassistant.components.go2rtc.Go2RtcWsClient", autospec=True
    ) as ws_client_mock:
        yield ws_client_mock.return_value


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    rest_client: AsyncMock,
    server: Mock,
) -> None:
    """Initialize the go2rtc integration."""
    await setup_integration(hass, config_entry)
