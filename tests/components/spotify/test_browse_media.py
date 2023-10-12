"""Test Spotify browse media."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.spotify.browse_media import build_item_response
from homeassistant.core import HomeAssistant


async def test_build_items_get_items(hass: HomeAssistant) -> None:
    """Test browse media get items."""
    with patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        user: dict[str, Any] = {"country": "US"}
        can_play_artist = True

        payload = {
            "media_content_type": "current_user_playlists",
            "media_content_id": "playlist_1",
        }

        assert spotify_mock
        assert user

        media: BrowseMedia = build_item_response(
            spotify_mock, user, payload, can_play_artist=can_play_artist
        )

        assert media


async def test_build_items_get_browsing_objects(hass: HomeAssistant) -> None:
    """Test browse media get items in objects."""
    with patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        user: dict[str, Any] = {"country": "US"}
        can_play_artist = True

        payload = {
            "media_content_type": "current_user_followed_artists",
            "media_content_id": "current_user_followed_artists_1",
        }

        assert spotify_mock
        assert user

        media: BrowseMedia = build_item_response(
            spotify_mock, user, payload, can_play_artist=can_play_artist
        )

        assert media


async def test_build_items_get_iterable_items(hass: HomeAssistant) -> None:
    """Test browse media get iterable items."""
    with patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        user: dict[str, Any] = {"country": "US"}
        can_play_artist = True

        payload = {
            "media_content_type": "current_user_recently_played",
            "media_content_id": "current_user_recently_played_1",
        }

        assert spotify_mock
        assert user

        media: BrowseMedia = build_item_response(
            spotify_mock, user, payload, can_play_artist=can_play_artist
        )

        assert media


async def test_build_items_get_playlist(hass: HomeAssistant) -> None:
    """Test browse media get playlist."""
    with patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        user: dict[str, Any] = {"country": "US"}
        can_play_artist = True

        payload = {
            "media_content_type": "playlist",
            "media_content_id": "playlist_1",
        }

        assert spotify_mock
        assert user

        media: BrowseMedia = build_item_response(
            spotify_mock, user, payload, can_play_artist=can_play_artist
        )

        assert media


async def test_build_items_get_objects(hass: HomeAssistant) -> None:
    """Test browse media get objects."""
    with patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        user: dict[str, Any] = {"country": "US"}
        can_play_artist = True

        payload = {
            "media_content_type": "category_playlists",
            "media_content_id": "category_playlists_1",
        }

        assert spotify_mock
        assert user

        media: BrowseMedia = build_item_response(
            spotify_mock, user, payload, can_play_artist=can_play_artist
        )

        assert media
        assert media.thumbnail
