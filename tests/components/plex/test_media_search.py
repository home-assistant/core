"""Tests for Plex server."""

from unittest.mock import patch

from plexapi.exceptions import BadRequest, NotFound
import pytest
import requests_mock

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components.plex.const import DOMAIN
from homeassistant.components.plex.errors import MediaNotFound
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_media_lookups(
    hass: HomeAssistant,
    mock_plex_server,
    requests_mock: requests_mock.Mocker,
    playqueue_created,
) -> None:
    """Test media lookups to Plex server."""
    # Plex Key searches
    media_player_id = hass.states.async_entity_ids("media_player")[0]
    requests_mock.post("/playqueues", text=playqueue_created)
    requests_mock.get("/player/playback/playMedia", status_code=200)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
            ATTR_MEDIA_CONTENT_ID: 1,
        },
        True,
    )
    with (
        pytest.raises(MediaNotFound) as excinfo,
        patch("plexapi.server.PlexServer.fetchItem", side_effect=NotFound),
    ):
        await hass.services.async_call(
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

    # Search with a different specified username
    with (
        patch(
            "plexapi.library.LibrarySection.search",
            __qualname__="search",
        ) as search,
        patch(
            "plexapi.myplex.MyPlexAccount.user",
            __qualname__="user",
        ) as plex_account_user,
    ):
        plex_account_user.return_value.get_token.return_value = "token"
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show", "username": "Kids"}',
            },
            True,
        )
        search.assert_called_with(**{"show.title": "TV Show", "libtype": "show"})
        plex_account_user.assert_called_with("Kids")

    # TV show searches
    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Not a Library", "show_name": "TV Show"}',
            },
            True,
        )
    assert "Library 'Not a Library' not found in" in str(excinfo.value)

    with patch(
        "plexapi.library.LibrarySection.search",
        __qualname__="search",
    ) as search:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show"}',
            },
            True,
        )
        search.assert_called_with(**{"show.title": "TV Show", "libtype": "show"})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "episode_name": "An Episode"}',
            },
            True,
        )
        search.assert_called_with(
            **{"episode.title": "An Episode", "libtype": "episode"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show", "season_number": 1}',
            },
            True,
        )
        search.assert_called_with(
            **{"show.title": "TV Show", "season.index": 1, "libtype": "season"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
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

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist"}',
            },
            True,
        )
        search.assert_called_with(**{"artist.title": "Artist", "libtype": "artist"})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "album_name": "Album"}',
            },
            True,
        )
        search.assert_called_with(**{"album.title": "Album", "libtype": "album"})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "track_name": "Track 3"}',
            },
            True,
        )
        search.assert_called_with(
            **{"artist.title": "Artist", "track.title": "Track 3", "libtype": "track"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )
        search.assert_called_with(
            **{"artist.title": "Artist", "album.title": "Album", "libtype": "album"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
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

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
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
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "video_name": "Movie 1"}',
            },
            True,
        )
        search.assert_called_with(**{"movie.title": "Movie 1", "libtype": None})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MOVIE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Movie 1"}',
            },
            True,
        )
        search.assert_called_with(title="Movie 1", libtype=None)

    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
                ATTR_MEDIA_CONTENT_ID: '{"title": "Movie 1"}',
            },
            True,
        )
    assert "Must specify 'library_name' for this search" in str(excinfo.value)

    with (
        pytest.raises(MediaNotFound) as excinfo,
        patch(
            "plexapi.library.LibrarySection.search",
            side_effect=BadRequest,
            __qualname__="search",
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Not a Movie"}',
            },
            True,
        )
    assert "Problem in query" in str(excinfo.value)

    # Playlist searches
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: '{"playlist_name": "Playlist 1"}',
        },
        True,
    )

    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: '{"playlist_name": "Not a Playlist"}',
            },
            True,
        )
    assert "Playlist 'Not a Playlist' not found" in str(excinfo.value)

    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: "{}",
            },
            True,
        )
    assert "Must specify 'playlist_name' for this search" in str(excinfo.value)
