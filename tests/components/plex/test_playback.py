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
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    SERVERS,
    SERVICE_PLAY_ON_SONOS,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_URL
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPTIONS, MOCK_SERVERS, SECONDARY_DATA

from tests.common import MockConfigEntry


async def test_sonos_playback(
    hass, mock_plex_server, requests_mock, playqueue_created, sonos_resources
):
    """Test playing media on a Sonos speaker."""
    server_id = mock_plex_server.machine_identifier
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
    requests_mock.get("https://sonos.plex.tv/resources", text=sonos_resources)
    requests_mock.get(
        "https://sonos.plex.tv/player/playback/playMedia", status_code=200
    )
    requests_mock.post("/playqueues", text=playqueue_created)
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="Speaker 2",
    ):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: "100",
            },
            True,
        )

    # Test success with dict
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="Speaker 2",
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

    # Test media lookup failure
    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="Speaker 2",
    ), patch("plexapi.server.PlexServer.fetchItem", side_effect=NotFound):
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
        return_value="Speaker 2",
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
        return_value="Speaker 2",
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


async def test_playback_multiple_servers(
    hass,
    setup_plex_server,
    requests_mock,
    caplog,
    empty_payload,
    playqueue_created,
    plex_server_accounts,
    plex_server_base,
    sonos_resources,
):
    """Test playing media when multiple servers available."""
    secondary_entry = MockConfigEntry(
        domain=DOMAIN,
        data=SECONDARY_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=SECONDARY_DATA["server_id"],
    )

    secondary_url = SECONDARY_DATA[PLEX_SERVER_CONFIG][CONF_URL]
    secondary_name = SECONDARY_DATA[CONF_SERVER]
    secondary_id = SECONDARY_DATA[CONF_SERVER_IDENTIFIER]
    requests_mock.get(
        secondary_url,
        text=plex_server_base.format(
            name=secondary_name, machine_identifier=secondary_id
        ),
    )
    requests_mock.get(f"{secondary_url}/accounts", text=plex_server_accounts)
    requests_mock.get(f"{secondary_url}/clients", text=empty_payload)
    requests_mock.get(f"{secondary_url}/status/sessions", text=empty_payload)

    await setup_plex_server()
    await setup_plex_server(config_entry=secondary_entry)

    requests_mock.get("https://sonos.plex.tv/resources", text=sonos_resources)
    requests_mock.get(
        "https://sonos.plex.tv/player/playback/playMedia", status_code=200
    )
    requests_mock.post("/playqueues", text=playqueue_created)

    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="Speaker 2",
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
        "Multiple Plex servers configured, choose with 'plex_server' key" in caplog.text
    )

    with patch.object(
        hass.components.sonos,
        "get_coordinator_name",
        return_value="Speaker 2",
    ):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            {
                ATTR_ENTITY_ID: "media_player.sonos_kitchen",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: f'{{"plex_server": "{MOCK_SERVERS[0][CONF_SERVER]}", "library_name": "Music", "artist_name": "Artist", "album_name": "Album"}}',
            },
            True,
        )
