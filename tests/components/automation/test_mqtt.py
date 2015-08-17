"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant.core as ha
import homeassistant.components.automation as automation
import homeassistant.components.automation.mqtt as mqtt
from homeassistant.const import CONF_PLATFORM

from tests.common import mock_mqtt_component, fire_mqtt_message


class TestAutomationState(unittest.TestCase):
    """ Test the event automation. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        mock_mqtt_component(self.hass)
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup_fails_if_no_topic(self):
        self.assertFalse(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

    def test_if_fires_on_topic_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                mqtt.CONF_TOPIC: 'test-topic',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', '')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_topic_and_payload_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                mqtt.CONF_TOPIC: 'test-topic',
                mqtt.CONF_PAYLOAD: 'hello',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', 'hello')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_topic_but_no_payload_match(self):
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                mqtt.CONF_TOPIC: 'test-topic',
                mqtt.CONF_PAYLOAD: 'hello',
                automation.CONF_SERVICE: 'test.automation'
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', 'no-hello')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
