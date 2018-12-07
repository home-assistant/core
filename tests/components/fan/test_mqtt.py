"""Test MQTT fans."""
import json

from homeassistant.setup import async_setup_component
from homeassistant.components import fan
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_UNAVAILABLE

from tests.common import async_fire_mqtt_message, MockConfigEntry, \
    async_mock_mqtt_component


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if command fails with command topic."""
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
        }
    })
    assert hass.states.get('fan.test') is None


async def test_default_availability_payload(hass, mqtt_mock):
    """Test the availability payload."""
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'availability_topic'
        }
    })

    state = hass.states.get('fan.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'online')
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is not STATE_UNAVAILABLE
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', 'offline')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'state-topic', '1')
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'online')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is not STATE_UNAVAILABLE


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test the availability payload."""
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'availability_topic',
            'payload_available': 'good',
            'payload_not_available': 'nogood'
        }
    })

    state = hass.states.get('fan.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'good')
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is not STATE_UNAVAILABLE
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', 'nogood')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'state-topic', '1')
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'good')
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is not STATE_UNAVAILABLE


async def test_discovery_removal_fan(hass, mqtt_mock, caplog):
    """Test removal of discovered fan."""
    entry = MockConfigEntry(domain='mqtt')
    await async_start(hass, 'homeassistant', {}, entry)
    data = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('fan.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('fan.beer')
    assert state is None


async def test_discovery_update_fan(hass, mqtt_mock, caplog):
    """Test removal of discovered fan."""
    entry = MockConfigEntry(domain='mqtt')
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "command_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('fan.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('fan.beer')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('fan.milk')
    assert state is None


async def test_unique_id(hass):
    """Test unique_id option only creates one fan per id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'state_topic': 'test-topic',
            'command_topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'state_topic': 'test-topic',
            'command_topic': 'test-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(fan.DOMAIN)) == 1


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT fan device registry integration."""
    entry = MockConfigEntry(domain='mqtt')
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'command_topic': 'test-command-topic',
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
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
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
