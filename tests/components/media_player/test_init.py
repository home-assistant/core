"""Test the base functions of the media player."""
import base64
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.const import TYPE_RESULT

from tests.common import mock_coro


async def test_get_image(hass, hass_ws_client):
    """Test get image via WS command."""
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
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result']['content_type'] == 'image/jpeg'
    assert msg['result']['content'] == \
        base64.b64encode(b'image').decode('utf-8')


async def test_get_image_http(hass, hass_client):
    """Test get image via http command."""
    await async_setup_component(hass, 'media_player', {
        'media_player': {
            'platform': 'demo'
        }
    })

    client = await hass_client()

    with patch('homeassistant.components.media_player.MediaPlayerDevice.'
               'async_get_media_image', return_value=mock_coro(
                   (b'image', 'image/jpeg'))):
        resp = await client.get('/api/media_player_proxy/media_player.bedroom')
        content = await resp.read()

    assert content == b'image'


async def test_get_image_http_url(hass, hass_client):
    """Test get image url via http command."""
    await async_setup_component(hass, 'media_player', {
        'media_player': {
            'platform': 'demo'
        }
    })

    client = await hass_client()

    with patch('homeassistant.components.media_player.MediaPlayerDevice.'
               'media_image_remotely_accessible', return_value=True):
        resp = await client.get('/api/media_player_proxy/media_player.bedroom',
                                allow_redirects=False)
        assert resp.headers['Location'] == \
            'https://img.youtube.com/vi/kxopViU98Xo/hqdefault.jpg'
