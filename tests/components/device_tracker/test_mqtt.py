"""
tests.components.device_tracker.test_mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the MQTT device tracker component.
"""
import unittest
import os

from homeassistant.components import device_tracker
from homeassistant.const import CONF_PLATFORM

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)


class TestComponentsDeviceTrackerMQTT(unittest.TestCase):
    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_new_message(self):
        dev_id = 'paulus'
        enttiy_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        topic = '/location/paulus'
        location = 'work'

        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                'devices': {dev_id: topic}
            }}))
        fire_mqtt_message(self.hass, topic, location)
        self.hass.pool.block_till_done()
        self.assertEqual(location, self.hass.states.get(enttiy_id).state)
