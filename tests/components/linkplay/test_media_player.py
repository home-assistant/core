"""Tests for the LinkPlay media player platform."""

from unittest.mock import MagicMock

from linkplay.consts import PlayingStatus
import pytest

from homeassistant.components.linkplay.media_player import LinkPlayMediaPlayerEntity


def _mock_linkplay_entity(
    album_art: str | None,
    status: PlayingStatus = PlayingStatus.PLAYING,
) -> LinkPlayMediaPlayerEntity:
    """Create a LinkPlay media player entity with mocked bridge data."""
    bridge = MagicMock()
    bridge.device.uuid = "test-uuid"
    bridge.device.playmode_support = []
    bridge.player.available_equalizer_modes = []
    bridge.player.album_art = album_art
    bridge.player.status = status
    return LinkPlayMediaPlayerEntity(bridge)


@pytest.mark.parametrize(
    "album_art", [None, "", "   ", "unknown", "Unknown", "none", "null"]
)
def test_media_image_url_ignores_unknown_album_art(album_art: str | None) -> None:
    """Test unknown album art values are not exposed as media image URLs."""
    entity = _mock_linkplay_entity(album_art)

    assert entity.media_image_url is None


def test_media_image_url_returns_album_art_for_playing_media() -> None:
    """Test album art is exposed while media is playing."""
    entity = _mock_linkplay_entity("http://example.com/album-art.jpg")

    assert entity.media_image_url == "http://example.com/album-art.jpg"


def test_media_image_url_returns_none_when_not_playing() -> None:
    """Test album art is hidden when media is stopped."""
    entity = _mock_linkplay_entity(
        "http://example.com/album-art.jpg", PlayingStatus.STOPPED
    )

    assert entity.media_image_url is None
