"""
tests.components.binary_sensor.test_mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests MQTT binary sensor.
"""
import unittest

import homeassistant.components.binary_sensor as binary_sensor
from tests.common import mock_mqtt_component, fire_mqtt_message
from homeassistant.const import (STATE_OFF, STATE_ON)

from tests.common import get_test_home_assistant


class TestSensorMQTT(unittest.TestCase):
    """ Test the MQTT sensor. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setting_sensor_value_via_mqtt_message(self):
        self.assertTrue(binary_sensor.setup(self.hass, {
            'binary_sensor': {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
            }
        }))

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'test-topic', 'OFF')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)
