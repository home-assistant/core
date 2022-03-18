"""Tests for the Sonos Media Player platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.plex.const import PLEX_URI_SCHEME
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError


async def test_plex_play_media(hass, async_autosetup_sonos):
    """Test playing media via the Plex integration."""
    media_player = "media_player.zone_a"
    media_content_id = (
        '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}'
    )

    with patch(
        "homeassistant.components.sonos.media_player.lookup_plex_media"
    ) as mock_lookup, patch(
        "soco.plugins.plex.PlexPlugin.add_to_queue"
    ) as mock_add_to_queue, patch(
        "homeassistant.components.sonos.media_player.SonosMediaPlayerEntity.set_shuffle"
    ) as mock_shuffle:
        # Test successful Plex service call
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{media_content_id}",
            },
            blocking=True,
        )

        assert len(mock_lookup.mock_calls) == 1
        assert len(mock_add_to_queue.mock_calls) == 1
        assert not mock_shuffle.called
        assert mock_lookup.mock_calls[0][1][1] == MEDIA_TYPE_MUSIC
        assert mock_lookup.mock_calls[0][1][2] == media_content_id

        # Test handling shuffle in payload
        mock_lookup.reset_mock()
        mock_add_to_queue.reset_mock()
        shuffle_media_content_id = '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album", "shuffle": 1}'

        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{shuffle_media_content_id}",
            },
            blocking=True,
        )

        assert mock_shuffle.called
        assert len(mock_lookup.mock_calls) == 1
        assert len(mock_add_to_queue.mock_calls) == 1
        assert mock_lookup.mock_calls[0][1][1] == MEDIA_TYPE_MUSIC
        assert mock_lookup.mock_calls[0][1][2] == media_content_id

        # Test failed Plex service call
        mock_lookup.reset_mock()
        mock_lookup.side_effect = HomeAssistantError
        mock_add_to_queue.reset_mock()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                MP_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: media_player,
                    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                    ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{media_content_id}",
                },
                blocking=True,
            )
        assert mock_lookup.called
        assert not mock_add_to_queue.called
