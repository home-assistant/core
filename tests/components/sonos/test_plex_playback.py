"""Tests for the Sonos Media Player platform."""

import json
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEnqueue,
    MediaType,
)
from homeassistant.components.plex import DOMAIN as PLEX_DOMAIN, PLEX_URI_SCHEME
from homeassistant.components.sonos.media_player import LONG_SERVICE_TIMEOUT
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockSoCo


async def test_plex_play_media(
    hass: HomeAssistant, soco: MockSoCo, async_autosetup_sonos
) -> None:
    """Test playing media via the Plex integration."""
    mock_plex_server = Mock()
    mock_lookup = mock_plex_server.lookup_media

    media_player = "media_player.zone_a"
    media_content_id = (
        '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}'
    )

    with (
        patch(
            "homeassistant.components.plex.services.get_plex_server",
            return_value=mock_plex_server,
        ),
        patch("soco.plugins.plex.PlexPlugin.add_to_queue") as mock_add_to_queue,
        patch(
            "homeassistant.components.sonos.media_player.SonosMediaPlayerEntity.set_shuffle"
        ) as mock_shuffle,
    ):
        # Test successful Plex service call
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{media_content_id}",
            },
            blocking=True,
        )

        assert len(mock_lookup.mock_calls) == 1
        assert len(mock_add_to_queue.mock_calls) == 1
        assert not mock_shuffle.called
        assert mock_lookup.mock_calls[0][1][0] == MediaType.MUSIC
        assert mock_lookup.mock_calls[0][2] == json.loads(media_content_id)
        assert soco.clear_queue.call_count == 1
        assert soco.play_from_queue.call_count == 1
        soco.play_from_queue.assert_called_with(0)

        # Test handling shuffle in payload
        mock_lookup.reset_mock()
        mock_add_to_queue.reset_mock()
        shuffle_media_content_id = (
            '{"library_name": "Music", "artist_name": "Artist", '
            '"album_name": "Album", "shuffle": 1}'
        )

        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{shuffle_media_content_id}",
            },
            blocking=True,
        )

        assert mock_shuffle.called
        assert len(mock_lookup.mock_calls) == 1
        assert len(mock_add_to_queue.mock_calls) == 1
        assert mock_lookup.mock_calls[0][1][0] == MediaType.MUSIC
        assert mock_lookup.mock_calls[0][2] == json.loads(media_content_id)

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
                    ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                    ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{media_content_id}",
                },
                blocking=True,
            )
        assert mock_lookup.called
        assert not mock_add_to_queue.called

        # Test new media browser payload format
        mock_lookup.reset_mock()
        mock_lookup.side_effect = None
        mock_add_to_queue.reset_mock()

        server_id = "unique_id_123"
        plex_item_key = 300

        with patch(
            "homeassistant.components.plex.services.get_plex_server",
            return_value=mock_plex_server,
        ):
            await hass.services.async_call(
                MP_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: media_player,
                    ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                    ATTR_MEDIA_CONTENT_ID: (
                        f"{PLEX_URI_SCHEME}{server_id}/{plex_item_key}?shuffle=1"
                    ),
                },
                blocking=True,
            )

        assert len(mock_lookup.mock_calls) == 1
        assert len(mock_add_to_queue.mock_calls) == 1
        assert mock_shuffle.called
        assert mock_lookup.mock_calls[0][1][0] == PLEX_DOMAIN
        assert mock_lookup.mock_calls[0][2] == {"plex_key": plex_item_key}

        mock_add_to_queue.reset_mock()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{media_content_id}",
                ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD,
            },
            blocking=True,
        )
        assert mock_add_to_queue.call_count == 1
        mock_add_to_queue.assert_called_with(
            mock_lookup(), timeout=LONG_SERVICE_TIMEOUT
        )

        soco.play_from_queue.reset_mock()
        mock_add_to_queue.reset_mock()
        mock_add_to_queue.return_value = 9
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: f"{PLEX_URI_SCHEME}{media_content_id}",
                ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY,
            },
            blocking=True,
        )
        assert mock_add_to_queue.call_count == 1
        mock_add_to_queue.assert_called_with(
            mock_lookup(), position=1, timeout=LONG_SERVICE_TIMEOUT
        )
        assert soco.play_from_queue.call_count == 1
        soco.play_from_queue.assert_called_with(mock_add_to_queue.return_value - 1)
