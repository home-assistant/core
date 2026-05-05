"""Tests for Apple TV media player streaming behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyatv.const import DeviceModel, FeatureName, FeatureState, Protocol
from pyatv.exceptions import ConnectionLostError, NotSupportedError, ProtocolError
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN, MediaType
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported

from .common import create_conf, mrp_service

from tests.common import MockConfigEntry

_ENTITY_ID = "media_player.living_room"
_URL = "http://192.168.1.100:8123/api/tts_proxy/abc.mp3"


def _feature_info(state: FeatureState) -> MagicMock:
    info = MagicMock()
    info.state = state
    return info


def _make_mock_atv(
    stream_file_state: FeatureState,
    play_url_state: FeatureState,
) -> MagicMock:
    atv = MagicMock()
    atv.close = MagicMock()
    atv.stream.stream_file = AsyncMock()
    atv.stream.play_url = AsyncMock()
    atv.push_updater = MagicMock()
    atv.device_info.model = DeviceModel.Gen4K
    atv.device_info.raw_model = "AppleTV6,2"
    atv.device_info.version = "15.0"
    atv.device_info.mac = "AA:BB:CC:DD:EE:FF"
    atv.features.in_state.return_value = False
    atv.features.all_features.return_value = {
        FeatureName.StreamFile: _feature_info(stream_file_state),
        FeatureName.PlayUrl: _feature_info(play_url_state),
    }
    return atv


async def _setup_config_entry(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    atv: MagicMock,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        unique_id="mrpid",
        data={
            CONF_ADDRESS: "127.0.0.1",
            CONF_NAME: "Living Room",
            "credentials": {str(Protocol.MRP.value): "mrp_creds"},
            "identifiers": ["mrpid"],
        },
    )
    entry.add_to_hass(hass)
    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())
    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch("homeassistant.components.apple_tv.connect", return_value=atv),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.fixture
def mock_atv() -> MagicMock:
    """Apple TV mock with StreamFile and PlayUrl both available."""
    return _make_mock_atv(FeatureState.Available, FeatureState.Available)


@pytest.fixture
def mock_atv_play_url_only() -> MagicMock:
    """Apple TV mock with only PlayUrl available."""
    return _make_mock_atv(FeatureState.Unsupported, FeatureState.Available)


@pytest.fixture
def mock_atv_no_streaming() -> MagicMock:
    """Apple TV mock with no streaming capability."""
    return _make_mock_atv(FeatureState.Unsupported, FeatureState.Unsupported)


@pytest.fixture
async def mock_config_entry(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    mock_atv: MagicMock,
) -> MockConfigEntry:
    """Config entry backed by a mock ATV with full streaming support."""
    return await _setup_config_entry(hass, mock_async_zeroconf, mock_atv)


@pytest.fixture
async def mock_config_entry_play_url_only(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    mock_atv_play_url_only: MagicMock,
) -> MockConfigEntry:
    """Config entry backed by a mock ATV that supports only PlayUrl."""
    return await _setup_config_entry(hass, mock_async_zeroconf, mock_atv_play_url_only)


@pytest.fixture
async def mock_config_entry_no_streaming(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    mock_atv_no_streaming: MagicMock,
) -> MockConfigEntry:
    """Config entry backed by a mock ATV with no streaming capability."""
    return await _setup_config_entry(hass, mock_async_zeroconf, mock_atv_no_streaming)


async def test_play_media_streams_when_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: MagicMock,
) -> None:
    """stream_file is used even when _playing is None (device idle)."""
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: _ENTITY_ID,
            "media_content_id": _URL,
            "media_content_type": MediaType.MUSIC,
        },
        blocking=True,
    )

    mock_atv.stream.stream_file.assert_called_once_with(_URL)


@pytest.mark.parametrize(
    ("exc_class", "expected_log"),
    [
        (NotSupportedError, "Streaming not supported"),
        (ConnectionLostError, "Failed to stream media"),
        (ProtocolError, "Failed to stream media"),
    ],
)
async def test_play_media_stream_file_exception_is_caught(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: MagicMock,
    exc_class: type[Exception],
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Exceptions raised by stream_file are caught and logged."""
    mock_atv.stream.stream_file.side_effect = exc_class("error")

    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: _ENTITY_ID,
            "media_content_id": _URL,
            "media_content_type": MediaType.MUSIC,
        },
        blocking=True,
    )

    assert expected_log in caplog.text


@pytest.mark.parametrize(
    ("exc_class", "expected_log"),
    [
        (NotSupportedError, "Streaming not supported"),
        (ConnectionLostError, "Failed to stream media"),
        (ProtocolError, "Failed to stream media"),
    ],
)
async def test_play_media_play_url_exception_is_caught(
    hass: HomeAssistant,
    mock_config_entry_play_url_only: MockConfigEntry,
    mock_atv_play_url_only: MagicMock,
    exc_class: type[Exception],
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Exceptions raised by play_url are caught and logged."""
    mock_atv_play_url_only.stream.play_url.side_effect = exc_class("error")

    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: _ENTITY_ID,
            "media_content_id": "http://192.168.1.100:8123/video.mp4",
            "media_content_type": MediaType.VIDEO,
        },
        blocking=True,
    )

    assert expected_log in caplog.text


async def test_play_media_no_streaming_capability_raises(
    hass: HomeAssistant,
    mock_config_entry_no_streaming: MockConfigEntry,
    mock_atv_no_streaming: MagicMock,
) -> None:
    """Service call is rejected when device has no streaming capability."""
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            MP_DOMAIN,
            "play_media",
            {
                ATTR_ENTITY_ID: _ENTITY_ID,
                "media_content_id": _URL,
                "media_content_type": MediaType.MUSIC,
            },
            blocking=True,
        )
    mock_atv_no_streaming.stream.stream_file.assert_not_called()
    mock_atv_no_streaming.stream.play_url.assert_not_called()
