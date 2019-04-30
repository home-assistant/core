"""The tests for the MQTT switch platform."""
import json
from unittest.mock import ANY

from asynctest import patch
import pytest

from homeassistant.components import mqtt, switch
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON, STATE_UNAVAILABLE)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry, async_fire_mqtt_message, async_mock_mqtt_component,
    mock_coro, mock_registry)
from tests.components.switch import common


@pytest.fixture
def mock_publish(hass):
    """Initialize components."""
    yield hass.loop.run_until_complete(async_mock_mqtt_component(hass))


async def test_controlling_state_via_topic(hass, mock_publish):
    """Test the controlling state via topic."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_on': 1,
            'payload_off': 0
        }
    })

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'state-topic', '1')

    state = hass.states.get('switch.test')
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, 'state-topic', '0')

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF


async def test_sending_mqtt_commands_and_optimistic(hass, mock_publish):
    """Test the sending MQTT commands in optimistic mode."""
    fake_state = ha.State('switch.test', 'on')

    with patch('homeassistant.helpers.restore_state.RestoreEntity'
               '.async_get_last_state',
               return_value=mock_coro(fake_state)):
        assert await async_setup_component(hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'command-topic',
                'payload_on': 'beer on',
                'payload_off': 'beer off',
                'qos': '2'
            }
        })

    state = hass.states.get('switch.test')
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, 'switch.test')

    mock_publish.async_publish.assert_called_once_with(
        'command-topic', 'beer on', 2, False)
    mock_publish.async_publish.reset_mock()
    state = hass.states.get('switch.test')
    assert state.state == STATE_ON

    await common.async_turn_off(hass, 'switch.test')

    mock_publish.async_publish.assert_called_once_with(
        'command-topic', 'beer off', 2, False)
    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF


async def test_controlling_state_via_topic_and_json_message(
        hass, mock_publish):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_on': 'beer on',
            'payload_off': 'beer off',
            'value_template': '{{ value_json.val }}'
        }
    })

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, 'state-topic', '{"val":"beer on"}')

    state = hass.states.get('switch.test')
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, 'state-topic', '{"val":"beer off"}')

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF


async def test_default_availability_payload(hass, mock_publish):
    """Test the availability payload."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'availability_topic',
            'payload_on': 1,
            'payload_off': 0
        }
    })

    state = hass.states.get('switch.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'online')

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', 'offline')

    state = hass.states.get('switch.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'state-topic', '1')

    state = hass.states.get('switch.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'online')

    state = hass.states.get('switch.test')
    assert state.state == STATE_ON


async def test_custom_availability_payload(hass, mock_publish):
    """Test the availability payload."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'availability_topic',
            'payload_on': 1,
            'payload_off': 0,
            'payload_available': 'good',
            'payload_not_available': 'nogood'
        }
    })

    state = hass.states.get('switch.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'good')

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', 'nogood')

    state = hass.states.get('switch.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'state-topic', '1')

    state = hass.states.get('switch.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability_topic', 'good')

    state = hass.states.get('switch.test')
    assert state.state == STATE_ON


async def test_custom_state_payload(hass, mock_publish):
    """Test the state payload."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'payload_on': 1,
            'payload_off': 0,
            'state_on': "HIGH",
            'state_off': "LOW",
        }
    })

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'state-topic', 'HIGH')

    state = hass.states.get('switch.test')
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, 'state-topic', 'LOW')

    state = hass.states.get('switch.test')
    assert state.state == STATE_OFF


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    state = hass.states.get('switch.test')

    assert state.attributes.get('val') == '100'


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    state = hass.states.get('switch.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')

    state = hass.states.get('switch.test')
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
    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    state = hass.states.get('switch.beer')
    assert state.attributes.get('val') == '100'

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    state = hass.states.get('switch.beer')
    assert state.attributes.get('val') == '100'

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    state = hass.states.get('switch.beer')
    assert state.attributes.get('val') == '75'


async def test_unique_id(hass):
    """Test unique id option only creates one switch per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'state_topic': 'test-topic',
            'command_topic': 'command-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'state_topic': 'test-topic',
            'command_topic': 'command-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    async_fire_mqtt_message(hass, 'test-topic', 'payload')

    assert len(hass.states.async_entity_ids()) == 2
    # all switches group is 1, unique id created is 1


async def test_discovery_removal_switch(hass, mqtt_mock, caplog):
    """Test removal of discovered switch."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data)
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            '')
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is None


async def test_discovery_update_switch(hass, mqtt_mock, caplog):
    """Test update of discovered switch."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('switch.milk')
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
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('switch.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('switch.beer')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT switch device registry integration."""
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
    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data)
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
    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Milk'


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'state_topic': 'test-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('switch.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity('switch.beer', new_entity_id='switch.milk')
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is None

    state = hass.states.get('switch.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
