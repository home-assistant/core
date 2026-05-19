"""Tests for Apple TV media player streaming behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyatv.const import DeviceModel, FeatureName, FeatureState, Protocol
from pyatv.exceptions import (
    BlockedStateError,
    ConnectionLostError,
    NotSupportedError,
    PlaybackError,
    ProtocolError,
)
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotSupported

from .common import create_conf, mrp_service

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

_ENTITY_ID = "media_player.living_room"
_MUSIC_URL = "http://192.168.1.100:8123/api/tts_proxy/abc.mp3"
_VIDEO_URL = "http://192.168.1.100:8123/video.mp4"


def _make_mock_atv(
    stream_file_state: FeatureState,
    play_url_state: FeatureState,
) -> AsyncMock:
    """Build an Apple TV mock with the requested streaming feature states."""
    atv = AsyncMock()
    atv.close = MagicMock()
    atv.features = MagicMock()
    atv.stream.stream_file = AsyncMock()
    atv.stream.play_url = AsyncMock()
    atv.push_updater = MagicMock()
    atv.device_info.model = DeviceModel.Gen4K
    atv.device_info.raw_model = "AppleTV6,2"
    atv.device_info.version = "15.0"
    atv.device_info.mac = "AA:BB:CC:DD:EE:FF"
    feature_states = {
        FeatureName.StreamFile: stream_file_state,
        FeatureName.PlayUrl: play_url_state,
    }
    atv.features.all_features.return_value = {
        feature: MagicMock(state=state) for feature, state in feature_states.items()
    }
    atv.features.in_state.side_effect = lambda state, feature: (
        feature_states.get(feature) == state
    )
    return atv


@pytest.fixture
def mock_atv(
    stream_file_state: FeatureState,
    play_url_state: FeatureState,
) -> AsyncMock:
    """Apple TV mock parameterized by streaming feature states."""
    return _make_mock_atv(stream_file_state, play_url_state)


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    mock_atv: AsyncMock,
) -> MockConfigEntry:
    """Set up the apple_tv integration with the mocked Apple TV."""
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
        patch("homeassistant.components.apple_tv.connect", return_value=mock_atv),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(
    (
        "stream_file_state",
        "play_url_state",
        "media_type",
        "media_id",
        "called_method",
    ),
    [
        (
            FeatureState.Available,
            FeatureState.Available,
            MediaType.MUSIC,
            _MUSIC_URL,
            "stream_file",
        ),
        (
            FeatureState.Unsupported,
            FeatureState.Available,
            MediaType.VIDEO,
            _VIDEO_URL,
            "play_url",
        ),
    ],
)
async def test_play_media_when_idle(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    media_type: MediaType,
    media_id: str,
    called_method: str,
) -> None:
    """Streaming path is selected from device feature state, not _playing.

    Before the fix, _is_feature_available returned False for an idle device
    (_playing is None), so play_media silently failed.
    """
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: _ENTITY_ID,
            "media_content_id": media_id,
            "media_content_type": media_type,
        },
        blocking=True,
    )

    getattr(mock_atv.stream, called_method).assert_called_once_with(media_id)


@pytest.mark.parametrize(
    (
        "stream_file_state",
        "play_url_state",
        "media_type",
        "media_id",
        "stream_attr",
    ),
    [
        (
            FeatureState.Available,
            FeatureState.Available,
            MediaType.MUSIC,
            _MUSIC_URL,
            "stream_file",
        ),
        (
            FeatureState.Unsupported,
            FeatureState.Available,
            MediaType.VIDEO,
            _VIDEO_URL,
            "play_url",
        ),
    ],
)
@pytest.mark.parametrize(
    ("exc_class", "expected_translation_key"),
    [
        (BlockedStateError, "stream_failed"),
        (ConnectionLostError, "stream_failed"),
        (NotSupportedError, "streaming_not_supported"),
        (PlaybackError, "stream_failed"),
        (ProtocolError, "stream_failed"),
    ],
)
async def test_play_media_raises_ha_error_on_pyatv_failure(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_atv: AsyncMock,
    media_type: MediaType,
    media_id: str,
    stream_attr: str,
    exc_class: type[Exception],
    expected_translation_key: str,
) -> None:
    """Pyatv streaming exceptions surface as a translated HomeAssistantError."""
    getattr(mock_atv.stream, stream_attr).side_effect = exc_class("error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            "play_media",
            {
                ATTR_ENTITY_ID: _ENTITY_ID,
                "media_content_id": media_id,
                "media_content_type": media_type,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_translation_key
    assert exc_info.value.translation_domain == DOMAIN


@pytest.mark.parametrize(
    ("stream_file_state", "play_url_state"),
    [(FeatureState.Unsupported, FeatureState.Unsupported)],
)
async def test_play_media_no_streaming_capability_raises(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """play_media is rejected when neither StreamFile nor PlayUrl is supported."""
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            MP_DOMAIN,
            "play_media",
            {
                ATTR_ENTITY_ID: _ENTITY_ID,
                "media_content_id": _MUSIC_URL,
                "media_content_type": MediaType.MUSIC,
            },
            blocking=True,
        )
    mock_atv.stream.stream_file.assert_not_called()
    mock_atv.stream.play_url.assert_not_called()


@pytest.mark.parametrize(
    ("stream_file_state", "play_url_state"),
    [(FeatureState.Available, FeatureState.Available)],
)
async def test_browse_media_uses_media_source_when_idle(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """async_browse_media routes to media_source when the device is idle.

    Before the fix, _is_feature_available returned False for an idle device, so
    async_browse_media fell back to the app list instead of the media browser.
    """
    browse_result = BrowseMedia(
        title="Media",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="",
        can_play=False,
        can_expand=True,
        children=[],
    )

    with patch(
        "homeassistant.components.apple_tv.media_player.media_source.async_browse_media",
        new_callable=AsyncMock,
        return_value=browse_result,
    ) as mock_browse:
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": _ENTITY_ID,
            }
        )
        response = await client.receive_json()

    assert response["success"]
    mock_browse.assert_called_once()
