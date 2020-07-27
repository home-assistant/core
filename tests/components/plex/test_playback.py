"""Tests for Plex player playback methods/services."""
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.plex.const import DOMAIN, SERVERS, SERVICE_PLAY_ON_SONOS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_sonos_playback(hass):
    """Test playing media on a Sonos speaker."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    # Test Sonos integration lookup failure
    with patch.object(
        hass.components.sonos, "get_coordinator_name", side_effect=HomeAssistantError
    ):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )

    # Test success with dict
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="media_player.sonos_kitchen",
    ), patch("plexapi.playqueue.PlayQueue.create"):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: "2",
            },
            True,
        )

    # Test success with plex_key
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="media_player.sonos_kitchen",
    ), patch("plexapi.playqueue.PlayQueue.create"):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )

    # Test invalid Plex server requested
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="media_player.sonos_kitchen",
    ):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"plex_server": "unknown_plex_server", "library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )

    # Test no speakers available
    with patch.object(
        loaded_server.account, "sonos_speaker", return_value=None
    ), patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="media_player.sonos_kitchen",
    ):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )
