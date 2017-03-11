"""The tests for dispatcher camera component."""
import asyncio

from homeassistant.setup import async_setup_component
from homeassistant.helpers.dispatcher import async_dispatcher_send


@asyncio.coroutine
def test_run_camera_setup(hass, test_client):
    """Test that it fetches the given dispatcher data."""
    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'dispatcher',
            'name': 'dispatcher',
            'signal': 'test_camera',
        }})

    client = yield from test_client(hass.http.app)

    async_dispatcher_send(hass, 'test_camera', b'test')
    yield from hass.async_block_till_done()

    resp = yield from client.get('/api/camera_proxy/camera.dispatcher')

    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'test'

    async_dispatcher_send(hass, 'test_camera', b'test2')
    yield from hass.async_block_till_done()

    resp = yield from client.get('/api/camera_proxy/camera.dispatcher')

    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'test2'
