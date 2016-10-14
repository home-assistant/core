"""The tests for the MQTT automation."""
import unittest

from homeassistant.bootstrap import _setup_component
import homeassistant.components.automation as automation
from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant)


class TestAutomationMQTT(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        mock_mqtt_component(self.hass)
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_topic_match(self):
        """Test if message is fired on topic match."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'mqtt',
                    'topic': 'test-topic'
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.platform }} - {{ trigger.topic }}'
                                ' - {{ trigger.payload }}'
                    },
                }
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', 'test_payload')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('mqtt - test-topic - test_payload',
                         self.calls[0].data['some'])

        automation.turn_off(self.hass)
        self.hass.block_till_done()
        fire_mqtt_message(self.hass, 'test-topic', 'test_payload')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_topic_and_payload_match(self):
        """Test if message is fired on topic and payload match."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        })

        fire_mqtt_message(self.hass, 'test-topic', 'hello')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_topic_but_no_payload_match(self):
        """Test if message is not fired on topic but no payload."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        })

        fire_mqtt_message(self.hass, 'test-topic', 'no-hello')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
