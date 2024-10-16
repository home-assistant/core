"""The tests for the go2rtc component."""

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock, patch

from go2rtc_client import Stream
from go2rtc_client.models import Producer
from go2rtc_client.ws import WebRTCAnswer, WebRTCOffer
import pytest

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    Camera,
    CameraEntityFeature,
)
from homeassistant.components.camera.const import StreamType
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.components.camera.webrtc import (
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCSendMessage,
)
from homeassistant.components.go2rtc import WebRTCProvider
from homeassistant.components.go2rtc.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

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


@pytest.mark.usefixtures("init_test_integration")
async def _test_setup(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    after_setup_fn: Callable[[], None],
) -> None:
    """Test the go2rtc config entry."""
    entity_id = "camera.test"
    camera = get_camera_from_entity_id(hass, entity_id)
    assert camera.frontend_stream_type == StreamType.HLS

    await setup_integration(hass, mock_config_entry)
    after_setup_fn()

    with patch(
        "homeassistant.components.go2rtc.Go2RtcWsClient", autospec=True
    ) as ws_client_mock:
        ws_client = ws_client_mock.return_value
        result_mock = Mock(spec_set=WebRTCSendMessage)

        async def test() -> None:
            await camera.async_handle_webrtc_offer(OFFER_SDP, "session_id", result_mock)
            ws_client.send.assert_called_once_with(WebRTCOffer(OFFER_SDP))
            ws_client.subscribe.assert_called_once()

            # Simulate the answer from the go2rtc server
            callback = ws_client.subscribe.call_args[0][0]
            callback(WebRTCAnswer(ANSWER_SDP))

            result_mock.assert_called_once_with(HAWebRTCAnswer(ANSWER_SDP))

        await test()

        mock_client.streams.add.assert_called_once_with(entity_id, "rtsp://stream")

        # If the stream is already added, the stream should not be added again.
        mock_client.streams.add.reset_mock()
        mock_client.streams.list.return_value = {
            entity_id: Stream([Producer("rtsp://stream")])
        }

        result_mock.reset_mock()
        ws_client.reset_mock()
        await test()

        mock_client.streams.add.assert_not_called()
        assert isinstance(camera._webrtc_provider, WebRTCProvider)

        # Set stream source to None and provider should be skipped
        mock_client.streams.list.return_value = {}
        camera.set_stream_source(None)
        with pytest.raises(
            HomeAssistantError,
            match="Camera does not support WebRTC",
        ):
            await camera.async_handle_webrtc_offer(OFFER_SDP, "session_id", result_mock)

        # Remove go2rtc config entry
        assert mock_config_entry.state is ConfigEntryState.LOADED
        await hass.config_entries.async_remove(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

        assert camera._webrtc_provider is None
        assert camera.frontend_stream_type == StreamType.HLS


@pytest.mark.usefixtures("init_test_integration")
async def test_setup_go_binary(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_server: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the go2rtc config entry with binary."""

    def after_setup() -> None:
        mock_server.assert_called_once_with(hass, "/usr/bin/go2rtc")
        mock_server.return_value.start.assert_called_once()

    await _test_setup(hass, mock_client, mock_config_entry, after_setup)

    mock_server.return_value.stop.assert_called_once()


@pytest.mark.usefixtures("init_test_integration")
async def test_setup_go(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_server: Mock,
) -> None:
    """Test the go2rtc config entry without binary."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_HOST: "http://localhost:1984/"},
    )

    def after_setup() -> None:
        mock_server.assert_not_called()

    await _test_setup(hass, mock_client, config_entry, after_setup)

    mock_server.assert_not_called()
