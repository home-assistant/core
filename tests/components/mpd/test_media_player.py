"""Tests for the MPD media player."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mpd.media_player import MpdDevice


@pytest.fixture
def mpd_device():
    """Return an MPD device with a mocked client."""
    with patch("homeassistant.components.mpd.media_player.MPDClient") as mock_client:
        device = MpdDevice("192.168.1.10", 6600, None, "test")
        device._client = mock_client.return_value
        yield device


@pytest.mark.parametrize(
    ("file", "expected_albumart"),
    [
        ("music/artist/album/track.mp3", True),
        ("/api/tts_proxy/12345.mp3", False),
        (
            "/api/tts_proxy/12345.mp3?authSig=abcdef",
            False,
        ),
        ("/media/local/music/track.mp3", False),
        (
            "/media/local/music/track.mp3?authSig=abcdef",
            False,
        ),
        ("https://example.com/music/track.mp3", True),
    ],
)
async def test_get_file_image_response(mpd_device, file, expected_albumart) -> None:
    """Test artwork retrieval for different media resources."""
    mpd_device._client.commands = AsyncMock(return_value=["readpicture", "albumart"])
    mpd_device._client.readpicture = AsyncMock(return_value=None)
    mpd_device._client.albumart = AsyncMock(return_value=None)

    response = await mpd_device._async_get_file_image_response(file)

    assert response is None
    mpd_device._client.readpicture.assert_awaited_once_with(file)

    if expected_albumart:
        mpd_device._client.albumart.assert_awaited_once_with(file)
    else:
        mpd_device._client.albumart.assert_not_awaited()
