"""Tests for Plex player playback methods/services."""
from plexapi.exceptions import BadRequest, NotFound

from homeassistant.components.demo import DOMAIN as DEMO_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.plex.const import (
    DOMAIN,
    SERVERS,
    SERVICE_PLAY_ON_OTHER,
    SERVICE_PLAY_ON_SONOS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


async def test_sonos_no_plex_pass(hass, mock_plex_server, entity_sources, caplog):
    """Test playing media on a Sonos speaker without a Plex Pass."""
    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="media_player.sonos_kitchen",
    ), patch.object(
        loaded_server.account, "sonos_speaker", side_effect=BadRequest
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

    assert (
        f"Plex server '{loaded_server.friendly_name}' does not have an active Plex Pass"
        in caplog.text
    )


async def test_sonos_playback(hass, mock_plex_server, entity_sources):
    """Test playing media on a Sonos speaker."""
    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    # Test Sonos integration lookup failure
    with patch.object(
        hass.components.sonos, "get_coordinator_name", side_effect=HomeAssistantError
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


async def test_playback_to_unsupported_integration(hass, caplog, setup_plex_server):
    """Test playing media on an unsupported integration."""
    assert await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    # Set up after demo to allow `media_player` platform to load
    await setup_plex_server()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_ON_OTHER,
        {
            ATTR_ENTITY_ID: "media_player.bedroom",
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
        },
        True,
    )
    assert f"{DEMO_DOMAIN} is not a supported integration" in caplog.text


async def test_playback_unknown_entity(hass, mock_plex_server, caplog):
    """Test playback on an unknown entity."""
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_ON_OTHER,
        {
            ATTR_ENTITY_ID: "media_player.unknown",
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
            ATTR_MEDIA_CONTENT_ID: '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
        },
        True,
    )
    assert "Entity not found:" in caplog.text
