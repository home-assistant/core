"""The tests for mqtt camera component."""
import asyncio

from homeassistant.setup import async_setup_component
import homeassistant.components.mqtt as mqtt


@asyncio.coroutine
def test_run_camera_setup(hass, test_client):
    """Test that it fetches the given dispatcher data."""
    topic = 'test/camera'
    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'mqtt',
            'topic': topic,
            'name': 'Test Camera',
        }})

    client = yield from test_client(hass.http.app)

    mqtt.publish(hass, topic, 0xFFD8FF)
    yield from hass.async_block_till_done()

    resp = yield from client.get('/api/camera_proxy/camera.test_camera')

    assert resp.status == 200
    body = yield from resp.text()
    assert body == '16767231'
