"""The tests for the MQTT switch platform."""
import json
from asynctest import patch
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE,\
    ATTR_ASSUMED_STATE
import homeassistant.core as ha
from homeassistant.components import switch, mqtt
from homeassistant.components.mqtt.discovery import async_start

from tests.common import (
    mock_coro, async_mock_mqtt_component, async_fire_mqtt_message,
    MockConfigEntry)
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
    assert STATE_OFF == state.state
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'state-topic', '1')
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_ON == state.state

    async_fire_mqtt_message(hass, 'state-topic', '0')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state


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
    assert STATE_ON == state.state
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    common.turn_on(hass, 'switch.test')
    await hass.async_block_till_done()

    mock_publish.async_publish.assert_called_once_with(
        'command-topic', 'beer on', 2, False)
    mock_publish.async_publish.reset_mock()
    state = hass.states.get('switch.test')
    assert STATE_ON == state.state

    common.turn_off(hass, 'switch.test')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_publish.async_publish.assert_called_once_with(
        'command-topic', 'beer off', 2, False)
    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state


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
    assert STATE_OFF == state.state

    async_fire_mqtt_message(hass, 'state-topic', '{"val":"beer on"}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_ON == state.state

    async_fire_mqtt_message(hass, 'state-topic', '{"val":"beer off"}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state


async def test_controlling_availability(hass, mock_publish):
    """Test the controlling state via topic."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        switch.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'state-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'availability_topic',
            'payload_on': 1,
            'payload_off': 0,
            'payload_available': 1,
            'payload_not_available': 0
        }
    })

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability_topic', '1')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', '0')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'state-topic', '1')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability_topic', '1')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_ON == state.state


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
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability_topic', 'online')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', 'offline')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'state-topic', '1')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability_topic', 'online')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_ON == state.state


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
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability_topic', 'good')
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'availability_topic', 'nogood')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'state-topic', '1')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability_topic', 'good')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_ON == state.state


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
    assert STATE_OFF == state.state
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'state-topic', 'HIGH')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_ON == state.state

    async_fire_mqtt_message(hass, 'state-topic', 'LOW')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.test')
    assert STATE_OFF == state.state


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
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 2
    # all switches group is 1, unique id created is 1


async def test_discovery_removal_switch(hass, mqtt_mock, caplog):
    """Test expansion of discovered switch."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "Beer",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is None


async def test_discovery_update_switch(hass, mqtt_mock, caplog):
    """Test expansion of discovered switch."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "status_topic": "test_topic",'
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
    await hass.async_block_till_done()

    state = hass.states.get('switch.beer')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('switch.milk')
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
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'
