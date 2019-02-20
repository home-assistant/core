"""The tests for mqtt camera component."""
import asyncio

from homeassistant.setup import async_setup_component

from tests.common import (
    async_mock_mqtt_component, async_fire_mqtt_message)


@asyncio.coroutine
def test_run_camera_setup(hass, aiohttp_client):
    """Test that it fetches the given payload."""
    topic = 'test/camera'
    yield from async_mock_mqtt_component(hass)
    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'mqtt',
            'topic': topic,
            'name': 'Test Camera',
        }})

    url = hass.states.get('camera.test_camera').attributes['entity_picture']

    async_fire_mqtt_message(hass, topic, 'beer')
    yield from hass.async_block_till_done()

    client = yield from aiohttp_client(hass.http.app)
    resp = yield from client.get(url)
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'beer'


@asyncio.coroutine
def test_unique_id(hass):
    """Test unique id option only creates one camera per unique_id."""
    yield from async_mock_mqtt_component(hass)
    yield from async_setup_component(hass, 'camera', {
        'camera': [{
            'platform': 'mqtt',
            'name': 'Test Camera 1',
            'topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test Camera 2',
            'topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    yield from hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1
