"""The tests for the MQTT switch platform."""
import json
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component, async_setup_component
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE,\
    ATTR_ASSUMED_STATE
import homeassistant.core as ha
from homeassistant.components import switch, mqtt
from homeassistant.components.mqtt.discovery import async_start

from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant, mock_coro,
    async_mock_mqtt_component, async_fire_mqtt_message, MockConfigEntry)
from tests.components.switch import common


class TestSwitchMQTT(unittest.TestCase):
    """Test the MQTT switch."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_controlling_state_via_topic(self):
        """Test the controlling state via topic."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_on': 1,
                'payload_off': 0
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_sending_mqtt_commands_and_optimistic(self):
        """Test the sending MQTT commands in optimistic mode."""
        fake_state = ha.State('switch.test', 'on')

        with patch('homeassistant.components.switch.mqtt.async_get_last_state',
                   return_value=mock_coro(fake_state)):
            assert setup_component(self.hass, switch.DOMAIN, {
                switch.DOMAIN: {
                    'platform': 'mqtt',
                    'name': 'test',
                    'command_topic': 'command-topic',
                    'payload_on': 'beer on',
                    'payload_off': 'beer off',
                    'qos': '2'
                }
            })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        common.turn_on(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'command-topic', 'beer on', 2, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        common.turn_off(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'command-topic', 'beer off', 2, False)
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_controlling_state_via_topic_and_json_message(self):
        """Test the controlling state via topic and JSON message."""
        assert setup_component(self.hass, switch.DOMAIN, {
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

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"beer on"}')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"beer off"}')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_controlling_availability(self):
        """Test the controlling state via topic."""
        assert setup_component(self.hass, switch.DOMAIN, {
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

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'availability_topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

    def test_default_availability_payload(self):
        """Test the availability payload."""
        assert setup_component(self.hass, switch.DOMAIN, {
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

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'availability_topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

    def test_custom_availability_payload(self):
        """Test the availability payload."""
        assert setup_component(self.hass, switch.DOMAIN, {
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

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'availability_topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

    def test_custom_state_payload(self):
        """Test the state payload."""
        assert setup_component(self.hass, switch.DOMAIN, {
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

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'state-topic', 'HIGH')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'state-topic', 'LOW')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)


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

    state = hass.states.get('switch.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/switch/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

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
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'
