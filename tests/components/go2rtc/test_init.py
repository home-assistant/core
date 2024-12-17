"""The tests for the go2rtc component."""

from collections.abc import Callable, Generator
import logging
from typing import NamedTuple
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.client_exceptions import ClientConnectionError, ServerConnectionError
from awesomeversion import AwesomeVersion
from go2rtc_client import Stream
from go2rtc_client.exceptions import Go2RtcClientError, Go2RtcVersionError
from go2rtc_client.models import Producer
from go2rtc_client.ws import (
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
import pytest
from webrtc_models import RTCIceCandidateInit

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
from homeassistant.components.default_config import DOMAIN as DEFAULT_CONFIG_DOMAIN
from homeassistant.components.go2rtc import WebRTCProvider
from homeassistant.components.go2rtc.const import (
    CONF_DEBUG_UI,
    DEBUG_UI_URL_MESSAGE,
    DOMAIN,
    RECOMMENDED_VERSION,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
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


@pytest.fixture(name="has_go2rtc_entry")
def has_go2rtc_entry_fixture() -> bool:
    """Fixture to control if a go2rtc config entry should be created."""
    return True


@pytest.fixture
def mock_go2rtc_entry(hass: HomeAssistant, has_go2rtc_entry: bool) -> None:
    """Mock a go2rtc onfig entry."""
    if not has_go2rtc_entry:
        return
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)


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
    issue_registry: ir.IssueRegistry,
    rest_client: AsyncMock,
    ws_client: Mock,
    config: ConfigType,
    after_setup_fn: Callable[[], None],
    camera: MockCamera,
) -> None:
    """Test the go2rtc config entry."""
    entity_id = camera.entity_id
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.HLS}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert issue_registry.async_get_issue(DOMAIN, "recommended_version") is None
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].state == ConfigEntryState.LOADED
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

    rest_client.streams.add.assert_called_once_with(
        entity_id,
        [
            "rtsp://stream",
            f"ffmpeg:{camera.entity_id}#audio=opus#query=log_level=debug",
        ],
    )

    # Stream exists but the source is different
    rest_client.streams.add.reset_mock()
    rest_client.streams.list.return_value = {
        entity_id: Stream([Producer("rtsp://different")])
    }

    receive_message_callback.reset_mock()
    ws_client.reset_mock()
    await test()

    rest_client.streams.add.assert_called_once_with(
        entity_id,
        [
            "rtsp://stream",
            f"ffmpeg:{camera.entity_id}#audio=opus#query=log_level=debug",
        ],
    )

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
    "init_test_integration",
    "mock_get_binary",
    "mock_is_docker_env",
    "mock_go2rtc_entry",
)
@pytest.mark.parametrize(
    ("config", "ui_enabled"),
    [
        ({DOMAIN: {}}, False),
        ({DOMAIN: {CONF_DEBUG_UI: True}}, True),
        ({DEFAULT_CONFIG_DOMAIN: {}}, False),
        ({DEFAULT_CONFIG_DOMAIN: {}, DOMAIN: {CONF_DEBUG_UI: True}}, True),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
async def test_setup_go_binary(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    rest_client: AsyncMock,
    ws_client: Mock,
    server: AsyncMock,
    server_start: Mock,
    server_stop: Mock,
    init_test_integration: MockCamera,
    has_go2rtc_entry: bool,
    config: ConfigType,
    ui_enabled: bool,
) -> None:
    """Test the go2rtc config entry with binary."""
    assert (len(hass.config_entries.async_entries(DOMAIN)) == 1) == has_go2rtc_entry

    def after_setup() -> None:
        server.assert_called_once_with(hass, "/usr/bin/go2rtc", enable_ui=ui_enabled)
        server_start.assert_called_once()

    await _test_setup_and_signaling(
        hass,
        issue_registry,
        rest_client,
        ws_client,
        config,
        after_setup,
        init_test_integration,
    )

    await hass.async_stop()
    server_stop.assert_called_once()


@pytest.mark.usefixtures("mock_go2rtc_entry")
@pytest.mark.parametrize(
    ("go2rtc_binary", "is_docker_env"),
    [
        ("/usr/bin/go2rtc", True),
        (None, False),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
async def test_setup(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    rest_client: AsyncMock,
    ws_client: Mock,
    server: Mock,
    init_test_integration: MockCamera,
    mock_get_binary: Mock,
    mock_is_docker_env: Mock,
    has_go2rtc_entry: bool,
) -> None:
    """Test the go2rtc config entry without binary."""
    assert (len(hass.config_entries.async_entries(DOMAIN)) == 1) == has_go2rtc_entry

    config = {DOMAIN: {CONF_URL: "http://localhost:1984/"}}

    def after_setup() -> None:
        server.assert_not_called()

    await _test_setup_and_signaling(
        hass,
        issue_registry,
        rest_client,
        ws_client,
        config,
        after_setup,
        init_test_integration,
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
            HAWebRTCCandidate(RTCIceCandidateInit("candidate")),
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
    await camera.async_on_webrtc_candidate(session_id, RTCIceCandidateInit("candidate"))
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

    await camera.async_on_webrtc_candidate(session_id, RTCIceCandidateInit("candidate"))
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
ERR_CONNECT_RETRY = (
    "Could not connect to go2rtc instance on http://localhost:1984/; Retrying"
)
ERR_START_SERVER = "Could not start go2rtc server"
ERR_UNSUPPORTED_VERSION = "The go2rtc server version is not supported"
_INVALID_CONFIG = "Invalid config for 'go2rtc': "
ERR_INVALID_URL = _INVALID_CONFIG + "invalid url"
ERR_EXCLUSIVE = _INVALID_CONFIG + DEBUG_UI_URL_MESSAGE
ERR_URL_REQUIRED = "Go2rtc URL required in non-docker installs"


@pytest.mark.parametrize(
    ("config", "go2rtc_binary", "is_docker_env"),
    [
        ({}, None, False),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
@pytest.mark.usefixtures(
    "mock_get_binary", "mock_go2rtc_entry", "mock_is_docker_env", "server"
)
async def test_non_user_setup_with_error(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup integration does not fail if not setup by user."""

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("config", "go2rtc_binary", "is_docker_env", "expected_log_message"),
    [
        ({DEFAULT_CONFIG_DOMAIN: {}}, None, True, ERR_BINARY_NOT_FOUND),
        ({DEFAULT_CONFIG_DOMAIN: {}}, "/usr/bin/go2rtc", True, ERR_START_SERVER),
        ({DOMAIN: {}}, None, False, ERR_URL_REQUIRED),
        ({DOMAIN: {}}, None, True, ERR_BINARY_NOT_FOUND),
        ({DOMAIN: {}}, "/usr/bin/go2rtc", True, ERR_START_SERVER),
        ({DOMAIN: {CONF_URL: "invalid"}}, None, True, ERR_INVALID_URL),
        (
            {DOMAIN: {CONF_URL: "http://localhost:1984", CONF_DEBUG_UI: True}},
            None,
            True,
            ERR_EXCLUSIVE,
        ),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
@pytest.mark.usefixtures(
    "mock_get_binary", "mock_go2rtc_entry", "mock_is_docker_env", "server"
)
async def test_setup_with_setup_error(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
    has_go2rtc_entry: bool,
    expected_log_message: str,
) -> None:
    """Test setup integration fails."""

    assert not await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert bool(hass.config_entries.async_entries(DOMAIN)) == has_go2rtc_entry
    assert expected_log_message in caplog.text


@pytest.mark.parametrize(
    ("config", "go2rtc_binary", "is_docker_env", "expected_log_message"),
    [
        ({DOMAIN: {CONF_URL: "http://localhost:1984/"}}, None, True, ERR_CONNECT),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
@pytest.mark.usefixtures(
    "mock_get_binary", "mock_go2rtc_entry", "mock_is_docker_env", "server"
)
async def test_setup_with_setup_entry_error(
    hass: HomeAssistant,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
    expected_log_message: str,
) -> None:
    """Test setup integration entry fails."""

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].state == ConfigEntryState.SETUP_ERROR
    assert expected_log_message in caplog.text


@pytest.mark.parametrize("config", [{DOMAIN: {CONF_URL: "http://localhost:1984/"}}])
@pytest.mark.parametrize(
    ("cause", "expected_config_entry_state", "expected_log_message"),
    [
        (ClientConnectionError(), ConfigEntryState.SETUP_RETRY, ERR_CONNECT_RETRY),
        (ServerConnectionError(), ConfigEntryState.SETUP_RETRY, ERR_CONNECT_RETRY),
        (None, ConfigEntryState.SETUP_ERROR, ERR_CONNECT),
        (Exception(), ConfigEntryState.SETUP_ERROR, ERR_CONNECT),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
@pytest.mark.usefixtures(
    "mock_get_binary", "mock_go2rtc_entry", "mock_is_docker_env", "server"
)
async def test_setup_with_retryable_setup_entry_error_custom_server(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    rest_client: AsyncMock,
    config: ConfigType,
    cause: Exception,
    expected_config_entry_state: ConfigEntryState,
    expected_log_message: str,
) -> None:
    """Test setup integration entry fails."""
    go2rtc_error = Go2RtcClientError()
    go2rtc_error.__cause__ = cause
    rest_client.validate_server_version.side_effect = go2rtc_error
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].state == expected_config_entry_state
    assert expected_log_message in caplog.text


@pytest.mark.parametrize("config", [{DOMAIN: {}}, {DEFAULT_CONFIG_DOMAIN: {}}])
@pytest.mark.parametrize(
    ("cause", "expected_config_entry_state", "expected_log_message"),
    [
        (ClientConnectionError(), ConfigEntryState.NOT_LOADED, ERR_START_SERVER),
        (ServerConnectionError(), ConfigEntryState.NOT_LOADED, ERR_START_SERVER),
        (None, ConfigEntryState.NOT_LOADED, ERR_START_SERVER),
        (Exception(), ConfigEntryState.NOT_LOADED, ERR_START_SERVER),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
@pytest.mark.usefixtures(
    "mock_get_binary", "mock_go2rtc_entry", "mock_is_docker_env", "server"
)
async def test_setup_with_retryable_setup_entry_error_default_server(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    rest_client: AsyncMock,
    has_go2rtc_entry: bool,
    config: ConfigType,
    cause: Exception,
    expected_config_entry_state: ConfigEntryState,
    expected_log_message: str,
) -> None:
    """Test setup integration entry fails."""
    go2rtc_error = Go2RtcClientError()
    go2rtc_error.__cause__ = cause
    rest_client.validate_server_version.side_effect = go2rtc_error
    assert not await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == has_go2rtc_entry
    for config_entry in config_entries:
        assert config_entry.state == expected_config_entry_state
    assert expected_log_message in caplog.text


@pytest.mark.parametrize("config", [{DOMAIN: {}}, {DEFAULT_CONFIG_DOMAIN: {}}])
@pytest.mark.parametrize(
    ("go2rtc_error", "expected_config_entry_state", "expected_log_message"),
    [
        (
            Go2RtcVersionError("1.9.4", "1.9.5", "2.0.0"),
            ConfigEntryState.SETUP_RETRY,
            ERR_UNSUPPORTED_VERSION,
        ),
    ],
)
@pytest.mark.parametrize("has_go2rtc_entry", [True, False])
@pytest.mark.usefixtures(
    "mock_get_binary", "mock_go2rtc_entry", "mock_is_docker_env", "server"
)
async def test_setup_with_version_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    rest_client: AsyncMock,
    config: ConfigType,
    go2rtc_error: Exception,
    expected_config_entry_state: ConfigEntryState,
    expected_log_message: str,
) -> None:
    """Test setup integration entry fails."""
    rest_client.validate_server_version.side_effect = [None, go2rtc_error]
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].state == expected_config_entry_state
    assert expected_log_message in caplog.text


async def test_config_entry_remove(hass: HomeAssistant) -> None:
    """Test config entry removed when neither default_config nor go2rtc is in config."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.parametrize("config", [{DOMAIN: {CONF_URL: "http://localhost:1984"}}])
@pytest.mark.usefixtures("server")
async def test_setup_with_recommended_version_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    rest_client: AsyncMock,
    config: ConfigType,
) -> None:
    """Test setup integration entry fails."""
    rest_client.validate_server_version.return_value = AwesomeVersion("1.9.5")
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify the issue is created
    issue = issue_registry.async_get_issue(DOMAIN, "recommended_version")
    assert issue
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.issue_id == "recommended_version"
    assert issue.translation_key == "recommended_version"
    assert issue.translation_placeholders == {
        "recommended_version": RECOMMENDED_VERSION,
        "current_version": "1.9.5",
    }
