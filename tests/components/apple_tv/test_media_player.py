"""Test apple_tv media player."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyatv.const import FeatureName, FeatureState
from pyatv.interface import MediaMetadata
import pytest

from homeassistant.components.apple_tv.media_player import AppleTvMediaPlayer
from homeassistant.components.media_player import ATTR_MEDIA_EXTRA, MediaType


def _make_player() -> AppleTvMediaPlayer:
    """Create an AppleTvMediaPlayer with a mocked atv."""
    player = AppleTvMediaPlayer("test", "test_id", MagicMock())
    player.atv = AsyncMock()

    # Make _is_feature_available return True for StreamFile by default
    features_mock = MagicMock()
    features_mock.in_state = MagicMock(return_value=True)
    player.atv.features = features_mock

    # _playing must be set so _is_feature_available works
    player._playing = MagicMock()

    return player


async def test_play_media_stream_file_passes_metadata() -> None:
    """Test that stream_file is called with MediaMetadata from extra dict."""
    player = _make_player()

    with patch(
        "homeassistant.components.apple_tv.media_player.is_streamable",
        return_value=True,
    ):
        await player.async_play_media(
            MediaType.MUSIC,
            "http://example.com/song.mp3",
            **{
                ATTR_MEDIA_EXTRA: {
                    "title": "Test Song",
                    "metadata": {
                        "artist": "Test Artist",
                        "album": "Test Album",
                    },
                }
            },
        )

    player.atv.stream.stream_file.assert_called_once()
    call_kwargs = player.atv.stream.stream_file.call_args

    assert call_kwargs.args[0] == "http://example.com/song.mp3"
    metadata: MediaMetadata = call_kwargs.kwargs["metadata"]
    assert isinstance(metadata, MediaMetadata)
    assert metadata.title == "Test Song"
    assert metadata.artist == "Test Artist"
    assert metadata.album == "Test Album"


async def test_play_media_stream_file_no_extra() -> None:
    """Test that stream_file is called with empty MediaMetadata when no extra provided."""
    player = _make_player()

    with patch(
        "homeassistant.components.apple_tv.media_player.is_streamable",
        return_value=True,
    ):
        await player.async_play_media(
            MediaType.MUSIC,
            "http://example.com/song.mp3",
        )

    player.atv.stream.stream_file.assert_called_once()
    call_kwargs = player.atv.stream.stream_file.call_args

    metadata: MediaMetadata = call_kwargs.kwargs["metadata"]
    assert isinstance(metadata, MediaMetadata)
    assert metadata.title is None
    assert metadata.artist is None
    assert metadata.album is None


async def test_play_media_stream_file_partial_metadata() -> None:
    """Test that stream_file handles partial metadata (title only)."""
    player = _make_player()

    with patch(
        "homeassistant.components.apple_tv.media_player.is_streamable",
        return_value=True,
    ):
        await player.async_play_media(
            MediaType.MUSIC,
            "http://example.com/song.mp3",
            **{
                ATTR_MEDIA_EXTRA: {
                    "title": "Only Title",
                }
            },
        )

    call_kwargs = player.atv.stream.stream_file.call_args
    metadata: MediaMetadata = call_kwargs.kwargs["metadata"]
    assert metadata.title == "Only Title"
    assert metadata.artist is None
    assert metadata.album is None


async def test_play_media_play_url_no_metadata() -> None:
    """Test that play_url is used when StreamFile is unavailable (no metadata support)."""
    player = _make_player()

    # StreamFile unavailable, PlayUrl available
    def feature_state(state, feature):
        if feature == FeatureName.StreamFile:
            return False
        if feature == FeatureName.PlayUrl:
            return True
        return False

    player.atv.features.in_state = MagicMock(side_effect=feature_state)

    with patch(
        "homeassistant.components.apple_tv.media_player.is_streamable",
        return_value=False,
    ):
        await player.async_play_media(
            MediaType.MUSIC,
            "http://example.com/song.mp3",
            **{
                ATTR_MEDIA_EXTRA: {
                    "title": "Test Song",
                    "metadata": {"artist": "Test Artist"},
                }
            },
        )

    player.atv.stream.stream_file.assert_not_called()
    player.atv.stream.play_url.assert_called_once_with("http://example.com/song.mp3")
