"""The tests for the go2rtc component."""

from collections.abc import Callable, Generator
import logging
from typing import NamedTuple
from unittest.mock import AsyncMock, Mock, patch

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
    StreamType,
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
)
from homeassistant.components.go2rtc import CONF_USE_BUILTIN, WebRTCProvider
from homeassistant.components.go2rtc.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
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
async def init_integration(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    mock_is_docker_env,
    mock_get_binary,
    server: Mock,
) -> None:
    """Initialize the go2rtc integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


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
    config: ConfigType,
    after_setup_fn: Callable[[], None],
    camera: MockCamera,
) -> None:
    """Test the go2rtc config entry."""
    entity_id = camera.entity_id
    assert camera.frontend_stream_type == StreamType.HLS

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    after_setup_fn()

    receive_message_callback = Mock(spec_set=WebRTCSendMessage)

    async def test() -> None:
        await camera.async_handle_async_webrtc_offer(
            OFFER_SDP, "session_id", receive_message_callback
        )
        ws_client.send.assert_called_once_with(
            WebRTCOffer(
                OFFER_SDP,
                camera.async_get_webrtc_client_configuration().configuration.ice_servers,
            )
        )
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
    receive_message_callback.reset_mock()
    camera.set_stream_source(None)
    await camera.async_handle_async_webrtc_offer(
        OFFER_SDP, "session_id", receive_message_callback
    )
    receive_message_callback.assert_called_once_with(
        WebRTCError("go2rtc_webrtc_offer_failed", "Camera has no stream source")
    )


@pytest.mark.usefixtures(
    "init_test_integration", "mock_get_binary", "mock_is_docker_env"
)
async def test_setup_go_binary(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    ws_client: Mock,
    server: AsyncMock,
    server_start: Mock,
    server_stop: Mock,
    init_test_integration: MockCamera,
) -> None:
    """Test the go2rtc config entry with binary."""

    def after_setup() -> None:
        server.assert_called_once_with(hass, "/usr/bin/go2rtc")
        server_start.assert_called_once()

    await _test_setup_and_signaling(
        hass, rest_client, ws_client, {DOMAIN: {}}, after_setup, init_test_integration
    )

    await hass.async_stop()
    server_stop.assert_called_once()


@pytest.mark.parametrize(
    ("go2rtc_binary", "is_docker_env"),
    [
        ("/usr/bin/go2rtc", True),
        (None, False),
    ],
)
async def test_setup_go(
    hass: HomeAssistant,
    rest_client: AsyncMock,
    ws_client: Mock,
    server: Mock,
    init_test_integration: MockCamera,
    mock_get_binary: Mock,
    mock_is_docker_env: Mock,
) -> None:
    """Test the go2rtc config entry without binary."""
    config = {DOMAIN: {CONF_URL: "http://localhost:1984/"}}

    def after_setup() -> None:
        server.assert_not_called()

    await _test_setup_and_signaling(
        hass, rest_client, ws_client, config, after_setup, init_test_integration
    )

    mock_get_binary.assert_not_called()
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
    receive_callback = Mock(spec_set=WebRTCSendMessage)
    camera = init_test_integration

    await camera.async_handle_async_webrtc_offer(
        OFFER_SDP, "session_id", receive_callback
    )
    ws_client.send.assert_called_once_with(
        WebRTCOffer(
            OFFER_SDP,
            camera.async_get_webrtc_client_configuration().configuration.ice_servers,
        )
    )
    ws_client.subscribe.assert_called_once()

    # Simulate messages from the go2rtc server
    send_callback = ws_client.subscribe.call_args[0][0]

    return Callbacks(receive_callback, send_callback)


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
    expected_message: WebRTCMessage,
) -> None:
    """Test receiving message from go2rtc server."""
    on_message, send_message = message_callbacks

    send_message(message)
    on_message.assert_called_once_with(expected_message)


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
    await init_test_integration.async_handle_async_webrtc_offer(
        OFFER_SDP, session_id, Mock()
    )
    ws_client.send.assert_called_once_with(
        WebRTCOffer(
            OFFER_SDP,
            camera.async_get_webrtc_client_configuration().configuration.ice_servers,
        )
    )
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
    with pytest.raises(KeyError):
        camera.close_webrtc_session(session_id)
    ws_client.close.assert_not_called()

    # Store session
    await init_test_integration.async_handle_async_webrtc_offer(
        OFFER_SDP, session_id, Mock()
    )
    ws_client.send.assert_called_once_with(
        WebRTCOffer(
            OFFER_SDP,
            camera.async_get_webrtc_client_configuration().configuration.ice_servers,
        )
    )

    # Close session
    camera.close_webrtc_session(session_id)
    ws_client.close.assert_called_once()

    # Close again should raise an error
    ws_client.reset_mock()
    with pytest.raises(KeyError):
        camera.close_webrtc_session(session_id)
    ws_client.close.assert_not_called()


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
@pytest.mark.usefixtures("mock_get_binary", "mock_is_docker_env", "server")
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
@pytest.mark.usefixtures("mock_get_binary", "mock_is_docker_env", "server")
async def test_setup_with_error(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
    expected_log_message: str,
) -> None:
    """Test setup integration fails."""

    assert not await async_setup_component(hass, DOMAIN, config)
    assert expected_log_message in caplog.text


async def test_setup_builtin_disabled(hass: HomeAssistant) -> None:
    """Test option to not use builtin go2rtc provider."""
    with patch(
        "homeassistant.components.go2rtc.async_register_webrtc_provider"
    ) as mock_register_provider:
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_USE_BUILTIN: False}}
        )
        await hass.async_block_till_done()

    assert mock_register_provider.call_count == 0
