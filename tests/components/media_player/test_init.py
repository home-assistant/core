"""Test the base functions of the media player."""
import base64
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import websocket_api

from tests.common import mock_coro


async def test_get_panels(hass, hass_ws_client):
    """Test get_panels command."""
    await async_setup_component(hass, 'media_player', {
        'media_player': {
            'platform': 'demo'
        }
    })

    client = await hass_ws_client(hass)

    with patch('homeassistant.components.media_player.MediaPlayerDevice.'
               'async_get_media_image', return_value=mock_coro(
                   (b'image', 'image/jpeg'))):
        await client.send_json({
            'id': 5,
            'type': 'media_player_thumbnail',
            'entity_id': 'media_player.bedroom',
        })

        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == websocket_api.TYPE_RESULT
    assert msg['success']
    assert msg['result']['content_type'] == 'image/jpeg'
    assert msg['result']['content'] == \
        base64.b64encode(b'image').decode('utf-8')
