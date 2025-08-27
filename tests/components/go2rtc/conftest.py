"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from awesomeversion import AwesomeVersion
from go2rtc_client.rest import _StreamClient, _WebRTCClient
import pytest

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.go2rtc.const import DOMAIN, RECOMMENDED_VERSION
from homeassistant.components.go2rtc.server import Server
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockCamera

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)

GO2RTC_PATH = "homeassistant.components.go2rtc"


@pytest.fixture
def rest_client() -> Generator[AsyncMock]:
    """Mock a go2rtc rest client."""
    with (
        patch(
            "homeassistant.components.go2rtc.Go2RtcRestClient", autospec=True
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


@pytest.fixture(name="is_docker_env")
def is_docker_env_fixture() -> bool:
    """Fixture to provide is_docker_env return value."""
    return True


@pytest.fixture
def mock_is_docker_env(is_docker_env: bool) -> Generator[Mock]:
    """Mock is_docker_env."""
    with patch(
        "homeassistant.components.go2rtc.is_docker_env",
        return_value=is_docker_env,
    ) as mock_is_docker_env:
        yield mock_is_docker_env


@pytest.fixture(name="go2rtc_binary")
def go2rtc_binary_fixture() -> str:
    """Fixture to provide go2rtc binary name."""
    return "/usr/bin/go2rtc"


@pytest.fixture
def mock_get_binary(go2rtc_binary: str) -> Generator[Mock]:
    """Mock _get_binary."""
    with patch(
        "homeassistant.components.go2rtc.shutil.which",
        return_value=go2rtc_binary,
    ) as mock_which:
        yield mock_which


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    mock_is_docker_env: Generator[Mock],
    mock_get_binary: Generator[Mock],
    server: Mock,
) -> None:
    """Initialize the go2rtc integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


TEST_DOMAIN = "test"


@pytest.fixture
def integration_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Test mock config entry."""
    entry = MockConfigEntry(domain=TEST_DOMAIN)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_test_integration(
    hass: HomeAssistant,
    integration_config_entry: ConfigEntry,
) -> MockCamera:
    """Initialize components."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.CAMERA]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, Platform.CAMERA
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )
    test_camera = MockCamera()
    setup_test_component_platform(
        hass, CAMERA_DOMAIN, [test_camera], from_config_entry=True
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", Mock())

    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(integration_config_entry.entry_id)
        await hass.async_block_till_done()

    return test_camera
