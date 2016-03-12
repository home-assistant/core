"""The tests for the MQTT automation."""
import unittest

import homeassistant.components.automation as automation
from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant)


class TestAutomationMQTT(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_old_config_if_fires_on_topic_match(self):
        """Test if message is fired on topic match."""
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'mqtt',
                'mqtt_topic': 'test-topic',
                'execute_service': 'test.automation'
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', '')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_fires_on_topic_and_payload_match(self):
        """Test if message is fired on topic and payload match."""
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'mqtt',
                'mqtt_topic': 'test-topic',
                'mqtt_payload': 'hello',
                'execute_service': 'test.automation'
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', 'hello')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_old_config_if_not_fires_on_topic_but_no_payload_match(self):
        """Test if message is not fired on topic but no payload."""
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'platform': 'mqtt',
                'mqtt_topic': 'test-topic',
                'mqtt_payload': 'hello',
                'execute_service': 'test.automation'
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', 'no-hello')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_topic_match(self):
        """Test if message is fired on topic match."""
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'mqtt',
                    'topic': 'test-topic'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', '')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_topic_and_payload_match(self):
        """Test if message is fired on topic and payload match."""
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'mqtt',
                    'topic': 'test-topic',
                    'payload': 'hello'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', 'hello')
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_topic_but_no_payload_match(self):
        """Test if message is not fired on topic but no payload."""
        self.assertTrue(automation.setup(self.hass, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'mqtt',
                    'topic': 'test-topic',
                    'payload': 'hello'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        }))

        fire_mqtt_message(self.hass, 'test-topic', 'no-hello')
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
