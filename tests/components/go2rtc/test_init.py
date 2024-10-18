"""The tests for the go2rtc component."""

from collections.abc import Callable
import logging
from typing import NamedTuple
from unittest.mock import AsyncMock, Mock

from go2rtc_client import Stream
from go2rtc_client.models import Producer
from go2rtc_client.ws import (
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
import pytest

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    Camera,
    CameraEntityFeature,
)
from homeassistant.components.camera.const import StreamType
from homeassistant.components.camera.webrtc import (
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
    WebRTCMessages,
    WebRTCSendMessage,
)
from homeassistant.components.go2rtc import WebRTCProvider
from homeassistant.components.go2rtc.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import CONF_URL
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
    test_camera = MockCamera()
    setup_test_component_platform(
        hass, CAMERA_DOMAIN, [test_camera], from_config_entry=True
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", Mock())

    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(integration_config_entry.entry_id)
        await hass.async_block_till_done()

    return test_camera


async def _test_setup_and_signaling(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    ws_client: Mock,
    go2rtc_config_entry: MockConfigEntry,
    after_setup_fn: Callable[[], None],
    camera: MockCamera,
) -> None:
    """Test the go2rtc config entry."""
    entity_id = camera.entity_id
    assert camera.frontend_stream_type == StreamType.HLS

    await setup_integration(hass, go2rtc_config_entry)
    after_setup_fn()

    receive_message_callback = Mock(spec_set=WebRTCSendMessage)

    async def test() -> None:
        await camera.async_handle_webrtc_offer(
            OFFER_SDP, "session_id", receive_message_callback
        )
        ws_client.send.assert_called_once_with(WebRTCOffer(OFFER_SDP))
        ws_client.subscribe.assert_called_once()

        # Simulate the answer from the go2rtc server
        callback = ws_client.subscribe.call_args[0][0]
        callback(WebRTCAnswer(ANSWER_SDP))
        receive_message_callback.assert_called_once_with(HAWebRTCAnswer(ANSWER_SDP))

    await test()

    rest_client.streams.add.assert_called_once_with(entity_id, "rtsp://stream")

    # If the stream is already added, the stream should not be added again.
    rest_client.streams.add.reset_mock()
    rest_client.streams.list.return_value = {
        entity_id: Stream([Producer("rtsp://stream")])
    }

    receive_message_callback.reset_mock()
    ws_client.reset_mock()
    await test()

    rest_client.streams.add.assert_not_called()
    assert isinstance(camera._webrtc_provider, WebRTCProvider)

    # Set stream source to None and provider should be skipped
    rest_client.streams.list.return_value = {}
    camera.set_stream_source(None)
    with pytest.raises(
        HomeAssistantError,
        match="Camera does not support WebRTC",
    ):
        await camera.async_handle_webrtc_offer(
            OFFER_SDP, "session_id", receive_message_callback
        )

    # Remove go2rtc config entry
    assert go2rtc_config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_remove(go2rtc_config_entry.entry_id)
    await hass.async_block_till_done()
    assert go2rtc_config_entry.state is ConfigEntryState.NOT_LOADED

    assert camera._webrtc_provider is None
    assert camera.frontend_stream_type == StreamType.HLS


async def test_setup_go_binary(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    ws_client: Mock,
    server: AsyncMock,
    config_entry: MockConfigEntry,
    init_test_integration: MockCamera,
) -> None:
    """Test the go2rtc config entry with binary."""

    def after_setup() -> None:
        server.assert_called_once_with(hass, "/usr/bin/go2rtc")
        server.return_value.start.assert_called_once()

    await _test_setup_and_signaling(
        hass, rest_client, ws_client, config_entry, after_setup, init_test_integration
    )

    server.return_value.stop.assert_called_once()


async def test_setup_go(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    ws_client: Mock,
    server: Mock,
    init_test_integration: MockCamera,
) -> None:
    """Test the go2rtc config entry without binary."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_URL: "http://localhost:1984/"},
    )

    def after_setup() -> None:
        server.assert_not_called()

    await _test_setup_and_signaling(
        hass, rest_client, ws_client, config_entry, after_setup, init_test_integration
    )

    server.assert_not_called()


class Callbacks(NamedTuple):
    """Callbacks for the test."""

    on_message: Mock
    send_message: Mock


@pytest.fixture
async def message_callbacks(
    ws_client: Mock,
    init_test_integration: MockCamera,
) -> Callbacks:
    """Prepare and return receive message callback."""
    receivce_callback = Mock(spec_set=WebRTCSendMessage)

    await init_test_integration.async_handle_webrtc_offer(
        OFFER_SDP, "session_id", receivce_callback
    )
    ws_client.send.assert_called_once_with(WebRTCOffer(OFFER_SDP))
    ws_client.subscribe.assert_called_once()

    # Simulate messages from the go2rtc server
    send_callback = ws_client.subscribe.call_args[0][0]

    return Callbacks(receivce_callback, send_callback)


@pytest.mark.parametrize(
    ("message", "expected_message"),
    [
        (
            WebRTCCandidate("candidate"),
            HAWebRTCCandidate("candidate"),
        ),
        (
            WebRTCAnswer(ANSWER_SDP),
            HAWebRTCAnswer(ANSWER_SDP),
        ),
        (
            WsError("error"),
            WebRTCError("go2rtc_webrtc_offer_failed", "error"),
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_receiving_messages_from_go2rtc_server(
    message_callbacks: Callbacks,
    message: ReceiveMessages,
    expected_message: WebRTCMessages,
) -> None:
    """Test receiving message from go2rtc server."""
    on_message, send_message = message_callbacks

    send_message(message)
    on_message.assert_called_once_with(expected_message)


@pytest.mark.usefixtures("init_integration")
async def test_receiving_unknown_message_from_go2rtc_server(
    message_callbacks: Callbacks,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test receiving unknown message from go2rtc server."""
    on_message, send_message = message_callbacks

    send_message({"type": "unknown"})
    on_message.assert_not_called()
    assert (
        "homeassistant.components.go2rtc",
        logging.WARNING,
        "Unknown message {'type': 'unknown'}",
    ) in caplog.record_tuples


@pytest.mark.usefixtures("init_integration")
async def test_on_candidate(
    ws_client: Mock,
    init_test_integration: MockCamera,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test frontend sending candidate to go2rtc server."""
    camera = init_test_integration
    session_id = "session_id"

    # Session doesn't exist
    await camera.async_on_webrtc_candidate(session_id, "candidate")
    assert (
        "homeassistant.components.go2rtc",
        logging.DEBUG,
        f"Unknown session {session_id}. Ignoring candidate",
    ) in caplog.record_tuples
    caplog.clear()

    # Store session
    await init_test_integration.async_handle_webrtc_offer(OFFER_SDP, session_id, Mock())
    ws_client.send.assert_called_once_with(WebRTCOffer(OFFER_SDP))
    ws_client.reset_mock()

    await camera.async_on_webrtc_candidate(session_id, "candidate")
    ws_client.send.assert_called_once_with(WebRTCCandidate("candidate"))
    assert caplog.record_tuples == []


@pytest.mark.usefixtures("init_integration")
async def test_close_session(
    ws_client: Mock,
    init_test_integration: MockCamera,
) -> None:
    """Test closing session."""
    camera = init_test_integration
    session_id = "session_id"

    # Session doesn't exist
    camera.close_webrtc_session(session_id)
    ws_client.close.assert_not_called()

    # Store session
    await init_test_integration.async_handle_webrtc_offer(OFFER_SDP, session_id, Mock())
    ws_client.send.assert_called_once_with(WebRTCOffer(OFFER_SDP))

    # Close session
    camera.close_webrtc_session(session_id)
    ws_client.close.assert_called_once()

    # Close again should not call close
    ws_client.reset_mock()
    camera.close_webrtc_session(session_id)
    ws_client.close.assert_not_called()
