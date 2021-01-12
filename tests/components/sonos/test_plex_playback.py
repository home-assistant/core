"""Tests for the Sonos Media Player platform."""
from unittest.mock import patch

from plexapi.myplex import MyPlexAccount
import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.plex.const import DOMAIN as PLEX_DOMAIN, SERVERS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError

from .test_media_player import setup_platform


async def test_plex_play_media(
    hass,
    config_entry,
    config,
    requests_mock,
    plextv_account,
    plex_empty_payload,
    plex_sonos_resources,
):
    """Test playing media via the Plex integration."""
    requests_mock.get("https://plex.tv/users/account", text=plextv_account)
    requests_mock.get("https://sonos.plex.tv/resources", text=plex_empty_payload)

    class MockPlexServer:
        """Mock a PlexServer instance."""

        def __init__(self, has_media=False):
            self.account = MyPlexAccount(token="token")
            self.friendly_name = "plex"
            if has_media:
                self.media = "media"
            else:
                self.media = None

        def create_playqueue(self, media, **kwargs):
            pass

        def lookup_media(self, content_type, **kwargs):
            return self.media

    await setup_platform(hass, config_entry, config)
    hass.data[PLEX_DOMAIN] = {SERVERS: {}}
    media_player = "media_player.zone_a"

    # Test Plex service call with media key
    with pytest.raises(HomeAssistantError) as excinfo:
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: "plex://5",
            },
            True,
        )
    assert "No Plex servers available" in str(excinfo.value)

    # Add a mocked Plex server with no media
    hass.data[PLEX_DOMAIN][SERVERS] = {"plex": MockPlexServer()}

    # Test Plex service call with dict
    with pytest.raises(HomeAssistantError) as excinfo:
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: 'plex://{"library_name": "Music", "artist_name": "Artist"}',
            },
            True,
        )
    assert "Plex media not found" in str(excinfo.value)

    # Add a mocked Plex server
    hass.data[PLEX_DOMAIN][SERVERS] = {"plex": MockPlexServer(has_media=True)}

    # Test Plex service call with no Sonos speakers
    requests_mock.get("https://sonos.plex.tv/resources", text=plex_empty_payload)
    with pytest.raises(HomeAssistantError) as excinfo:
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: 'plex://{"library_name": "Music", "artist_name": "Artist"}',
            },
            True,
        )
    assert "Sonos speaker 'Zone A' is not associated with" in str(excinfo.value)

    # Test successful Plex service call
    account = hass.data[PLEX_DOMAIN][SERVERS]["plex"].account
    requests_mock.get("https://sonos.plex.tv/resources", text=plex_sonos_resources)

    with patch.object(account, "_sonos_cache_timestamp", 0), patch(
        "plexapi.sonos.PlexSonosClient.playMedia"
    ):
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: 'plex://{"plex_server": "plex", "library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )
