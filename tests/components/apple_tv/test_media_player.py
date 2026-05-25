"""Tests for the Apple TV media player."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

ENTITY_ID = "media_player.living_room_living_room"

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
