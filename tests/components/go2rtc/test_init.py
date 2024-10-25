"""The tests for the go2rtc component."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, Mock, patch

from go2rtc_client import Stream, WebRTCSdpAnswer, WebRTCSdpOffer
from go2rtc_client.models import Producer
import pytest

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    Camera,
    CameraEntityFeature,
)
from homeassistant.components.camera.const import StreamType
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.components.go2rtc import WebRTCProvider
from homeassistant.components.go2rtc.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)

TEST_DOMAIN = "test"

# The go2rtc provider does not inspect the details of the offer and answer,
# and is only a pass through.
OFFER_SDP = "v=0\r\no=carol 28908764872 28908764872 IN IP4 100.3.6.6\r\n..."
ANSWER_SDP = "v=0\r\no=bob 2890844730 2890844730 IN IP4 host.example.com\r\n..."


class MockCamera(Camera):
    """Mock Camera Entity."""

    _attr_name = "Test"
    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM

    def __init__(self) -> None:
        """Initialize the mock entity."""
        super().__init__()
        self._stream_source: str | None = "rtsp://stream"

    def set_stream_source(self, stream_source: str | None) -> None:
        """Set the stream source."""
        self._stream_source = stream_source

    async def stream_source(self) -> str | None:
        """Return the source of the stream.

        This is used by cameras with CameraEntityFeature.STREAM
        and StreamType.HLS.
        """
        return self._stream_source


@pytest.fixture
def integration_entity() -> MockCamera:
    """Mock Camera Entity."""
    return MockCamera()


@pytest.fixture
def integration_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Test mock config entry."""
    entry = MockConfigEntry(domain=TEST_DOMAIN)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="go2rtc_binary")
def go2rtc_binary_fixture() -> str:
    """Fixture to provide go2rtc binary name."""
    return "/usr/bin/go2rtc"


@pytest.fixture
def mock_get_binary(go2rtc_binary) -> Generator[Mock]:
    """Mock _get_binary."""
    with patch(
        "homeassistant.components.go2rtc.shutil.which",
        return_value=go2rtc_binary,
    ) as mock_which:
        yield mock_which


@pytest.fixture(name="is_docker_env")
def is_docker_env_fixture() -> bool:
    """Fixture to provide is_docker_env return value."""
    return True


@pytest.fixture
def mock_is_docker_env(is_docker_env) -> Generator[Mock]:
    """Mock is_docker_env."""
    with patch(
        "homeassistant.components.go2rtc.is_docker_env",
        return_value=is_docker_env,
    ) as mock_is_docker_env:
        yield mock_is_docker_env


@pytest.fixture
async def init_test_integration(
    hass: HomeAssistant,
    integration_config_entry: ConfigEntry,
    integration_entity: MockCamera,
) -> None:
    """Initialize components."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [CAMERA_DOMAIN]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, CAMERA_DOMAIN
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
    setup_test_component_platform(
        hass, CAMERA_DOMAIN, [integration_entity], from_config_entry=True
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", Mock())

    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(integration_config_entry.entry_id)
        await hass.async_block_till_done()

    return integration_config_entry


async def _test_setup(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    config: ConfigType,
    after_setup_fn: Callable[[], None],
) -> None:
    """Test the go2rtc config entry."""
    entity_id = "camera.test"
    camera = get_camera_from_entity_id(hass, entity_id)
    assert camera.frontend_stream_type == StreamType.HLS

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    after_setup_fn()

    mock_client.webrtc.forward_whep_sdp_offer.return_value = WebRTCSdpAnswer(ANSWER_SDP)

    answer = await camera.async_handle_web_rtc_offer(OFFER_SDP)
    assert answer == ANSWER_SDP

    mock_client.webrtc.forward_whep_sdp_offer.assert_called_once_with(
        entity_id, WebRTCSdpOffer(OFFER_SDP)
    )
    mock_client.streams.add.assert_called_once_with(entity_id, "rtsp://stream")

    # If the stream is already added, the stream should not be added again.
    mock_client.streams.add.reset_mock()
    mock_client.streams.list.return_value = {
        entity_id: Stream([Producer("rtsp://stream")])
    }

    answer = await camera.async_handle_web_rtc_offer(OFFER_SDP)
    assert answer == ANSWER_SDP
    mock_client.streams.add.assert_not_called()
    assert mock_client.webrtc.forward_whep_sdp_offer.call_count == 2
    assert isinstance(camera._webrtc_providers[0], WebRTCProvider)

    # Set stream source to None and provider should be skipped
    mock_client.streams.list.return_value = {}
    camera.set_stream_source(None)
    with pytest.raises(
        HomeAssistantError,
        match="WebRTC offer was not accepted by the supported providers",
    ):
        await camera.async_handle_web_rtc_offer(OFFER_SDP)


@pytest.mark.usefixtures(
    "init_test_integration", "mock_get_binary", "mock_is_docker_env"
)
async def test_setup_go_binary(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_server: AsyncMock,
    mock_server_start: Mock,
    mock_server_stop: Mock,
) -> None:
    """Test the go2rtc config entry with binary."""

    def after_setup() -> None:
        mock_server.assert_called_once_with(hass, "/usr/bin/go2rtc")
        mock_server_start.assert_called_once()

    await _test_setup(hass, mock_client, {DOMAIN: {}}, after_setup)

    await hass.async_stop()
    mock_server_stop.assert_called_once()


@pytest.mark.parametrize(
    ("go2rtc_binary", "is_docker_env"),
    [
        ("/usr/bin/go2rtc", True),
        (None, False),
    ],
)
@pytest.mark.usefixtures("init_test_integration")
async def test_setup_go(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_server: Mock,
    mock_get_binary: Mock,
    mock_is_docker_env: Mock,
) -> None:
    """Test the go2rtc config entry without binary."""
    config = {DOMAIN: {CONF_URL: "http://localhost:1984/"}}

    def after_setup() -> None:
        mock_server.assert_not_called()

    await _test_setup(hass, mock_client, config, after_setup)

    mock_get_binary.assert_not_called()
    mock_get_binary.assert_not_called()
    mock_server.assert_not_called()


ERR_BINARY_NOT_FOUND = "Could not find go2rtc docker binary"
ERR_CONNECT = "Could not connect to go2rtc instance"
ERR_INVALID_URL = "Invalid config for 'go2rtc': invalid url"
ERR_URL_REQUIRED = "Go2rtc URL required in non-docker installs"


@pytest.mark.parametrize(
    ("config", "go2rtc_binary", "is_docker_env"),
    [
        ({}, None, False),
    ],
)
@pytest.mark.usefixtures("mock_get_binary", "mock_is_docker_env", "mock_server")
async def test_non_user_setup_with_error(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup integration does not fail if not setup by user."""

    assert await async_setup_component(hass, DOMAIN, config)


@pytest.mark.parametrize(
    ("config", "go2rtc_binary", "is_docker_env", "expected_log_message"),
    [
        ({}, None, True, ERR_BINARY_NOT_FOUND),
        ({}, "/usr/bin/go2rtc", True, ERR_CONNECT),
        ({DOMAIN: {}}, None, False, ERR_URL_REQUIRED),
        ({DOMAIN: {}}, None, True, ERR_BINARY_NOT_FOUND),
        ({DOMAIN: {}}, "/usr/bin/go2rtc", True, ERR_CONNECT),
        ({DOMAIN: {CONF_URL: "invalid"}}, None, True, ERR_INVALID_URL),
        ({DOMAIN: {CONF_URL: "http://localhost:1984/"}}, None, True, ERR_CONNECT),
    ],
)
@pytest.mark.usefixtures("mock_get_binary", "mock_is_docker_env", "mock_server")
async def test_setup_with_error(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
    expected_log_message: str,
) -> None:
    """Test setup integration fails."""

    assert not await async_setup_component(hass, DOMAIN, config)
    assert expected_log_message in caplog.text
