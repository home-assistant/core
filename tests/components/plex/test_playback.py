"""Tests for Plex player playback methods/services."""
from unittest.mock import patch

from plexapi.exceptions import NotFound

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.plex.const import (
    CONF_SERVER,
    DOMAIN,
    SERVERS,
    SERVICE_PLAY_ON_SONOS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPTIONS, SECONDARY_DATA

from tests.common import MockConfigEntry


async def test_sonos_playback(hass, mock_plex_server):
    """Test playing media on a Sonos speaker."""
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
                ATTR_MEDIA_CONTENT_ID: "2",
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
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )

    # Test media lookup failure
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="media_player.sonos_kitchen",
    ), patch.object(mock_plex_server, "fetchItem", side_effect=NotFound):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: "999",
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
    ), patch(
        "plexapi.playqueue.PlayQueue.create"
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


async def test_playback_multiple_servers(hass, mock_websocket, setup_plex_server):
    """Test playing media when multiple servers available."""
    secondary_entry = MockConfigEntry(
        domain=DOMAIN,
        data=SECONDARY_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=SECONDARY_DATA["server_id"],
    )

    await setup_plex_server()
    await setup_plex_server(config_entry=secondary_entry)

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
                ATTR_MEDIA_CONTENT_ID: f'{{"plex_server": "{SECONDARY_DATA[CONF_SERVER]}", "library_name": "Music", "artist_name": "Artist", "album_name": "Album"}}',
            },
            True,
        )
