"""Tests for Plex server."""
from unittest.mock import patch

from plexapi.exceptions import BadRequest, NotFound
import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_VIDEO,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.plex.const import DOMAIN
from homeassistant.components.plex.errors import MediaNotFound
from homeassistant.const import ATTR_ENTITY_ID


async def test_media_lookups(hass, mock_plex_server, requests_mock, playqueue_created):
    """Test media lookups to Plex server."""
    # Plex Key searches
    media_player_id = hass.states.async_entity_ids("media_player")[0]
    requests_mock.post("/playqueues", text=playqueue_created)
    requests_mock.get("/player/playback/playMedia", status_code=200)

    assert await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
            ATTR_MEDIA_CONTENT_ID: 1,
        },
        True,
    )
    with pytest.raises(MediaNotFound) as excinfo:
        with patch("plexapi.server.PlexServer.fetchItem", side_effect=NotFound):
            assert await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: media_player_id,
                    ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
                    ATTR_MEDIA_CONTENT_ID: 123,
                },
                True,
            )
    assert "Media for key 123 not found" in str(excinfo.value)

    # TV show searches
    with pytest.raises(MediaNotFound) as excinfo:
        payload = '{"library_name": "Not a Library", "show_name": "TV Show"}'
        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_EPISODE,
                ATTR_MEDIA_CONTENT_ID: payload,
            },
            True,
        )
    assert "Library 'Not a Library' not found in" in str(excinfo.value)

    with patch("plexapi.library.LibrarySection.search") as search:
        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show"}',
            },
            True,
        )
        search.assert_called_with(**{"show.title": "TV Show", "libtype": "show"})

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "episode_name": "An Episode"}',
            },
            True,
        )
        search.assert_called_with(
            **{"episode.title": "An Episode", "libtype": "episode"}
        )

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show", "season_number": 1}',
            },
            True,
        )
        search.assert_called_with(
            **{"show.title": "TV Show", "season.index": 1, "libtype": "season"}
        )

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show", "season_number": 1, "episode_number": 3}',
            },
            True,
        )
        search.assert_called_with(
            **{
                "show.title": "TV Show",
                "season.index": 1,
                "episode.index": 3,
                "libtype": "episode",
            }
        )

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist"}',
            },
            True,
        )
        search.assert_called_with(**{"artist.title": "Artist", "libtype": "artist"})

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "album_name": "Album"}',
            },
            True,
        )
        search.assert_called_with(**{"album.title": "Album", "libtype": "album"})

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "track_name": "Track 3"}',
            },
            True,
        )
        search.assert_called_with(
            **{"artist.title": "Artist", "track.title": "Track 3", "libtype": "track"}
        )

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )
        search.assert_called_with(
            **{"artist.title": "Artist", "album.title": "Album", "libtype": "album"}
        )

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album", "track_number": 3}',
            },
            True,
        )
        search.assert_called_with(
            **{
                "artist.title": "Artist",
                "album.title": "Album",
                "track.index": 3,
                "libtype": "track",
            }
        )

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album", "track_name": "Track 3"}',
            },
            True,
        )
        search.assert_called_with(
            **{
                "artist.title": "Artist",
                "album.title": "Album",
                "track.title": "Track 3",
                "libtype": "track",
            }
        )

        # Movie searches
        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_VIDEO,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "video_name": "Movie 1"}',
            },
            True,
        )
        search.assert_called_with(**{"movie.title": "Movie 1", "libtype": None})

        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Movie 1"}',
            },
            True,
        )
        search.assert_called_with(**{"title": "Movie 1", "libtype": None})

    with pytest.raises(MediaNotFound) as excinfo:
        payload = '{"title": "Movie 1"}'
        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_VIDEO,
                ATTR_MEDIA_CONTENT_ID: payload,
            },
            True,
        )
    assert "Must specify 'library_name' for this search" in str(excinfo.value)

    with pytest.raises(MediaNotFound) as excinfo:
        payload = '{"library_name": "Movies", "title": "Not a Movie"}'
        with patch("plexapi.library.LibrarySection.search", side_effect=BadRequest):
            assert await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: media_player_id,
                    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_VIDEO,
                    ATTR_MEDIA_CONTENT_ID: payload,
                },
                True,
            )
    assert "Problem in query" in str(excinfo.value)

    # Playlist searches
    assert await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: '{"playlist_name": "Playlist 1"}',
        },
        True,
    )

    with pytest.raises(MediaNotFound) as excinfo:
        payload = '{"playlist_name": "Not a Playlist"}'
        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: payload,
            },
            True,
        )
    assert "Playlist 'Not a Playlist' not found" in str(excinfo.value)

    with pytest.raises(MediaNotFound) as excinfo:
        payload = "{}"
        assert await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: payload,
            },
            True,
        )
    assert "Must specify 'playlist_name' for this search" in str(excinfo.value)
