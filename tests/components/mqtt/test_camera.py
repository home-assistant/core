"""The tests for mqtt camera component."""
from unittest.mock import ANY

from homeassistant.components import camera, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry, async_fire_mqtt_message, async_mock_mqtt_component,
    mock_registry)


async def test_run_camera_setup(hass, aiohttp_client):
    """Test that it fetches the given payload."""
    topic = 'test/camera'
    await async_mock_mqtt_component(hass)
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'mqtt',
            'topic': topic,
            'name': 'Test Camera',
        }})

    url = hass.states.get('camera.test_camera').attributes['entity_picture']

    async_fire_mqtt_message(hass, topic, 'beer')

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(url)
    assert resp.status == 200
    body = await resp.text()
    assert body == 'beer'


async def test_unique_id(hass):
    """Test unique id option only creates one camera per unique_id."""
    await async_mock_mqtt_component(hass)
    await async_setup_component(hass, 'camera', {
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
    assert len(hass.states.async_all()) == 1


async def test_discovery_removal_camera(hass, mqtt_mock, caplog):
    """Test removal of discovered camera."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "Beer",'
        '  "topic": "test_topic"}'
    )

    async_fire_mqtt_message(hass, 'homeassistant/camera/bla/config',
                            data)
    await hass.async_block_till_done()

    state = hass.states.get('camera.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/camera/bla/config',
                            '')
    await hass.async_block_till_done()

    state = hass.states.get('camera.beer')
    assert state is None


async def test_discovery_update_camera(hass, mqtt_mock, caplog):
    """Test update of discovered camera."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "topic": "test_topic"}'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "topic": "test_topic"}'
    )

    async_fire_mqtt_message(hass, 'homeassistant/camera/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('camera.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/camera/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('camera.beer')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('camera.milk')
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "topic": "test_topic"}'
    )

    async_fire_mqtt_message(hass, 'homeassistant/camera/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('camera.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/camera/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('camera.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('camera.beer')
    assert state is None


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, camera.DOMAIN, {
        camera.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('camera.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 1
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, None)
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity('camera.beer', new_entity_id='camera.milk')
    await hass.async_block_till_done()

    state = hass.states.get('camera.beer')
    assert state is None

    state = hass.states.get('camera.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 1
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, None)
