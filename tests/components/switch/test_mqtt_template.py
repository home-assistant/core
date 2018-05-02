"""The tests for the MQTT template switch platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ASSUMED_STATE
import homeassistant.components.switch as switch
from tests.common import (
    mock_mqtt_component, get_test_home_assistant)


class TestSwitchMQTT(unittest.TestCase):
    """Test the MQTT template switch."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop everything that was started."""
        self.hass.stop()

    def test_sending_mqtt_commands_with_templated_payloads(self):
        """Test the sending MQTT commands in optimistic mode."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt_template',
                'name': 'test',
                'command_topic': 'command-topic',
                'payload_on_template':
                    "on,{{ states.sensor.duration_1.state }}",
                'payload_off_template':
                    "off,{{ states.sensor.duration_2.state }}",
                'qos': '2'
            }
        })

        self.hass.states.set('sensor.duration_1', '1234')
        self.hass.states.set('sensor.duration_2', '5678')

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        switch.turn_on(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'command-topic', 'on,1234', 2, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        switch.turn_off(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'command-topic', 'off,5678', 2, False)
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
