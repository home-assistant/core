"""Tests for the Sonos Media Player platform."""
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


async def test_plex_play_media(hass, config_entry, config):
    """Test join/unjoin requires control access."""
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

    # Test Plex service call with dict
    with pytest.raises(HomeAssistantError) as excinfo:
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: 'plex://{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}',
            },
            True,
        )
    assert "No Plex servers available" in str(excinfo.value)
