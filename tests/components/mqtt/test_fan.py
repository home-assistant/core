"""Test MQTT fans."""
import json
from unittest.mock import ANY

from homeassistant.components import fan, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry, async_fire_mqtt_message, async_mock_mqtt_component,
    mock_registry)


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
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.state is not STATE_UNAVAILABLE


async def test_discovery_removal_fan(hass, mqtt_mock, caplog):
    """Test removal of discovered fan."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
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
    """Test update of discovered fan."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
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


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('fan.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('fan.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('fan.beer')
    assert state is None


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    await hass.async_block_till_done()
    state = hass.states.get('fan.test')

    assert '100' == state.attributes.get('val')


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    await hass.async_block_till_done()
    state = hass.states.get('fan.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')
    await hass.async_block_till_done()

    state = hass.states.get('fan.test')
    assert state.attributes.get('val') is None
    assert 'Erroneous JSON: This is not JSON' in caplog.text


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('fan.beer')
    assert '100' == state.attributes.get('val')

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('fan.beer')
    assert '100' == state.attributes.get('val')

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('fan.beer')
    assert '75' == state.attributes.get('val')


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
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
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


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    config = {
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
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/fan/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Milk'


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, fan.DOMAIN, {
        fan.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'state_topic': 'test-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('fan.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity('fan.beer', new_entity_id='fan.milk')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('fan.beer')
    assert state is None

    state = hass.states.get('fan.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
