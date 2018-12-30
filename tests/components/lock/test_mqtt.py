"""The tests for the MQTT lock platform."""
import json

from homeassistant.setup import async_setup_component
from homeassistant.const import (
    STATE_LOCKED, STATE_UNLOCKED, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
from homeassistant.components import lock, mqtt
from homeassistant.components.mqtt.discovery import async_start

from tests.common import (
    async_fire_mqtt_message, async_mock_mqtt_component, MockConfigEntry)


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling state via topic."""
    assert await async_setup_component(hass, lock.DOMAIN, {
        lock.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_lock': 'LOCK',
            'payload_unlock': 'UNLOCK'
        }
    })

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNLOCKED
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'state-topic', 'LOCK')
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is STATE_LOCKED

    async_fire_mqtt_message(hass, 'state-topic', 'UNLOCK')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNLOCKED


async def test_controlling_state_via_topic_and_json_message(hass, mqtt_mock):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(hass, lock.DOMAIN, {
        lock.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_lock': 'LOCK',
            'payload_unlock': 'UNLOCK',
            'value_template': '{{ value_json.val }}'
        }
    })

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNLOCKED

    async_fire_mqtt_message(hass, 'state-topic', '{"val":"LOCK"}')
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is STATE_LOCKED

    async_fire_mqtt_message(hass, 'state-topic', '{"val":"UNLOCK"}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNLOCKED


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    assert await async_setup_component(hass, lock.DOMAIN, {
        lock.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_lock': 'LOCK',
            'payload_unlock': 'UNLOCK',
            'availability_topic': 'availability-topic'
        }
    })

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'online')
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is not STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'offline')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNAVAILABLE


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(hass, lock.DOMAIN, {
        lock.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_lock': 'LOCK',
            'payload_unlock': 'UNLOCK',
            'availability_topic': 'availability-topic',
            'payload_available': 'good',
            'payload_not_available': 'nogood'
        }
    })

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'good')
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is not STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'nogood')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('lock.test')
    assert state.state is STATE_UNAVAILABLE


async def test_unique_id(hass):
    """Test unique id option only creates one light per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, lock.DOMAIN, {
        lock.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'status_topic': 'test-topic',
            'command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'status_topic': 'test-topic',
            'command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })
    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(lock.DOMAIN)) == 1


async def test_discovery_removal_lock(hass, mqtt_mock, caplog):
    """Test removal of discovered lock."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/lock/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('lock.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/lock/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('lock.beer')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT lock device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'command_topic': 'test-topic',
        'device': {
            'identifiers': ['helloworld'],
            'connections': [
                ["mac", "02:5b:26:a8:dc:12"],
            ],
            'manufacturer': 'Whatever',
            'name': 'Beer',
            'model': 'Glass',
            'sw_version': '0.1-beta',
        },
        'unique_id': 'veryunique'
    })
    async_fire_mqtt_message(hass, 'homeassistant/lock/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'
