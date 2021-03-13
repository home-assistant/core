"""Tests for Plex player playback methods/services."""
from unittest.mock import patch

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID


async def test_media_player_playback(
    hass, setup_plex_server, requests_mock, playqueue_created, player_plexweb_resources
):
    """Test playing media on a Plex media_player."""
    requests_mock.get("http://1.2.3.5:32400/resources", text=player_plexweb_resources)

    await setup_plex_server()

    media_player = "media_player.plex_plex_web_chrome"
    requests_mock.post("/playqueues", text=playqueue_created)
    requests_mock.get("/player/playback/playMedia", status_code=200)

    # Test movie success
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Movie 1" }',
        },
        True,
    )

    # Test movie incomplete dict
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies"}',
        },
        True,
    )

    # Test movie failure with options
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Does not exist" }',
        },
        True,
    )

    # Test movie failure with nothing found
    with patch("plexapi.library.LibrarySection.search", return_value=None):
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MOVIE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Does not exist" }',
            },
            True,
        )

    # Test movie success with dict
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
        },
        True,
    )

    # Test TV show episoe lookup failure
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_EPISODE,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "TV Shows", "show_name": "TV Show", "season_number": 1, "episode_number": 99}',
        },
        True,
    )

    # Test track name lookup failure
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album", "track_name": "Not a track"}',
        },
        True,
    )

    # Test media lookup failure by key
    requests_mock.get("/library/metadata/999", status_code=404)
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            ATTR_MEDIA_CONTENT_ID: "999",
        },
        True,
    )

    # Test invalid Plex server requested
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            ATTR_MEDIA_CONTENT_ID: '{"plex_server": "unknown_plex_server", "library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
        },
        True,
    )
