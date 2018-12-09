"""The tests for the MQTT lock platform."""
from homeassistant.setup import async_setup_component
from homeassistant.const import (
    STATE_LOCKED, STATE_UNLOCKED, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
from homeassistant.components import lock, mqtt
from homeassistant.components.mqtt.discovery import async_start

from tests.common import async_fire_mqtt_message, MockConfigEntry


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
