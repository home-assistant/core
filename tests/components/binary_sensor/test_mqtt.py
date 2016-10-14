"""The tests for the  MQTT binary sensor platform."""
import unittest

from homeassistant.bootstrap import _setup_component
import homeassistant.components.binary_sensor as binary_sensor
from tests.common import mock_mqtt_component, fire_mqtt_message
from homeassistant.const import (STATE_OFF, STATE_ON)

from tests.common import get_test_home_assistant


class TestSensorMQTT(unittest.TestCase):
    """Test the MQTT sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setting_sensor_value_via_mqtt_message(self):
        """Test the setting of the value via MQTT."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'test-topic', 'OFF')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_valid_sensor_class(self):
        """Test the setting of a valid sensor class."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'sensor_class': 'motion',
                'state_topic': 'test-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('motion', state.attributes.get('sensor_class'))

    def test_invalid_sensor_class(self):
        """Test the setting of an invalid sensor class."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'sensor_class': 'abc123',
                'state_topic': 'test-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertIsNone(state.attributes.get('sensor_class'))
