"""Tests for the Apple TV media player."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from pyatv.const import FeatureName, FeatureState
from pyatv.exceptions import (
    BlockedStateError,
    ConnectionLostError,
    InvalidStateError,
    NotSupportedError,
    OperationTimeoutError,
    PlaybackError,
    ProtocolError,
)
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.typing import WebSocketGenerator

ENTITY_ID = "media_player.living_room_living_room"
_MUSIC_URL = "http://example.local:8123/api/tts_proxy/abc.mp3"
_VIDEO_URL = "http://example.local:8123/video.mp4"

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("play_item", "expected_stream_arg"),
    [
        (
            PlayMedia(
                url="/api/media_source_proxy/song.mp3",
                mime_type="audio/mp3",
                path=Path("/media/song.mp3"),
            ),
            "/media/song.mp3",
        ),
        (
            PlayMedia(
                url="https://example.com/song.mp3",
                mime_type="audio/mp3",
            ),
            "https://example.com/song.mp3",
        ),
    ],
)
async def test_play_media_from_media_source(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    play_item: PlayMedia,
    expected_stream_arg: str,
) -> None:
    """Stream resolved media via its local path when present, otherwise via the URL."""
    with patch(
        "homeassistant.components.apple_tv.media_player.media_source.async_resolve_media",
        return_value=play_item,
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://local/song.mp3",
            },
            blocking=True,
        )

    mock_atv.stream.stream_file.assert_awaited_once_with(expected_stream_arg)


@pytest.mark.parametrize("media_type", [MediaType.APP, MediaType.URL])
async def test_play_media_launches_app(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    media_type: MediaType,
) -> None:
    """App and URL media types launch the corresponding app on the device."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: "com.netflix.Netflix",
        },
        blocking=True,
    )

    mock_atv.apps.launch_app.assert_awaited_once_with("com.netflix.Netflix")
    mock_atv.stream.stream_file.assert_not_called()


@pytest.mark.parametrize(
    ("media_type", "media_id", "called_method", "stream_file_state"),
    [
        pytest.param(
            MediaType.MUSIC,
            _MUSIC_URL,
            "stream_file",
            FeatureState.Available,
            id="music_via_raop",
        ),
        pytest.param(
            MediaType.VIDEO,
            _VIDEO_URL,
            "play_url",
            FeatureState.Unsupported,
            id="video_via_airplay",
        ),
    ],
)
async def test_play_media_selects_streaming_method(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    media_type: MediaType,
    media_id: str,
    called_method: str,
    stream_file_state: FeatureState,
) -> None:
    """Streaming path is selected from device feature state, not _playing."""
    mock_atv.features.set_state(FeatureName.StreamFile, stream_file_state)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )

    getattr(mock_atv.stream, called_method).assert_awaited_once_with(media_id)


async def test_play_media_falls_back_to_play_url(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
) -> None:
    """When StreamFile is unavailable, play_url is used for video."""
    mock_atv.features.set_state(FeatureName.StreamFile, FeatureState.Unsupported)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
            ATTR_MEDIA_CONTENT_ID: _VIDEO_URL,
        },
        blocking=True,
    )

    mock_atv.stream.play_url.assert_awaited_once_with(_VIDEO_URL)
    mock_atv.stream.stream_file.assert_not_called()


async def test_play_media_raises_when_no_streaming_method(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
) -> None:
    """Raise HomeAssistantError when no streaming method is available."""
    mock_atv.features.set_state(FeatureName.StreamFile, FeatureState.Unsupported)
    mock_atv.features.set_state(FeatureName.PlayUrl, FeatureState.Unsupported)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: _MUSIC_URL,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "streaming_not_supported"
    assert exc_info.value.translation_domain == DOMAIN
    mock_atv.stream.stream_file.assert_not_called()
    mock_atv.stream.play_url.assert_not_called()


@pytest.mark.parametrize(
    ("stream_attr", "media_type", "media_id", "stream_file_state"),
    [
        (
            "stream_file",
            MediaType.MUSIC,
            _MUSIC_URL,
            FeatureState.Available,
        ),
        (
            "play_url",
            MediaType.VIDEO,
            _VIDEO_URL,
            FeatureState.Unsupported,
        ),
    ],
)
@pytest.mark.parametrize(
    ("exc_class", "expected_translation_key"),
    [
        (BlockedStateError, "stream_failed"),
        (ConnectionLostError, "stream_failed"),
        (InvalidStateError, "stream_failed"),
        (NotSupportedError, "streaming_not_supported"),
        (OperationTimeoutError, "stream_failed"),
        (PlaybackError, "stream_failed"),
        (ProtocolError, "stream_failed"),
    ],
)
async def test_play_media_raises_ha_error_on_pyatv_failure(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    stream_attr: str,
    media_type: MediaType,
    media_id: str,
    stream_file_state: FeatureState,
    exc_class: type[Exception],
    expected_translation_key: str,
) -> None:
    """Pyatv streaming exceptions surface as a translated HomeAssistantError."""
    mock_atv.features.set_state(FeatureName.StreamFile, stream_file_state)
    getattr(mock_atv.stream, stream_attr).side_effect = exc_class("error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: media_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_translation_key
    assert exc_info.value.translation_domain == DOMAIN


async def test_browse_media_uses_media_source(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """async_browse_media routes to media_source when streaming is available."""
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
                "entity_id": ENTITY_ID,
            }
        )
        response = await client.receive_json()

    assert response["success"]
    mock_browse.assert_called_once()
