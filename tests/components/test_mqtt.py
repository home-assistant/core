"""
tests.test_component_mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests MQTT component.
"""
import unittest
from unittest import mock
import socket

import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    EVENT_CALL_SERVICE, ATTR_DOMAIN, ATTR_SERVICE, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP)

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)


class TestDemo(unittest.TestCase):
    """ Test the demo module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant(1)
        mock_mqtt_component(self.hass)
        self.calls = []

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def record_calls(self, *args):
        self.calls.append(args)

    def test_client_starts_on_home_assistant_start(self):
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.pool.block_till_done()
        self.assertTrue(mqtt.MQTT_CLIENT.start.called)

    def test_client_stops_on_home_assistant_start(self):
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.pool.block_till_done()
        self.hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        self.hass.pool.block_till_done()
        self.assertTrue(mqtt.MQTT_CLIENT.stop.called)

    def test_setup_fails_if_no_broker_config(self):
        self.assertFalse(mqtt.setup(self.hass, {mqtt.DOMAIN: {}}))

    def test_setup_fails_if_no_connect_broker(self):
        with mock.patch('homeassistant.components.mqtt.MQTT',
                        side_effect=socket.error()):
            self.assertFalse(mqtt.setup(self.hass, {mqtt.DOMAIN: {
                mqtt.CONF_BROKER: 'test-broker',
            }}))

    def test_publish_calls_service(self):
        self.hass.bus.listen_once(EVENT_CALL_SERVICE, self.record_calls)

        mqtt.publish(self.hass, 'test-topic', 'test-payload')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic', self.calls[0][0].data[mqtt.ATTR_TOPIC])
        self.assertEqual('test-payload', self.calls[0][0].data[mqtt.ATTR_PAYLOAD])

    def test_service_call_without_topic_does_not_publush(self):
        self.hass.bus.fire(EVENT_CALL_SERVICE, {
            ATTR_DOMAIN: mqtt.DOMAIN,
            ATTR_SERVICE: mqtt.SERVICE_PUBLISH
        })
        self.hass.pool.block_till_done()
        self.assertTrue(not mqtt.MQTT_CLIENT.publish.called)

    def test_subscribe_topic(self):
        mqtt.subscribe(self.hass, 'test-topic', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_not_match(self):
        mqtt.subscribe(self.hass, 'test-topic', self.record_calls)

        fire_mqtt_message(self.hass, 'another-test-topic', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_subscribe_topic_level_wildcard(self):
        mqtt.subscribe(self.hass, 'test-topic/+/on', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic/bier/on', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic/bier/on', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_level_wildcard_no_subtree_match(self):
        mqtt.subscribe(self.hass, 'test-topic/+/on', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic/bier', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_subscribe_topic_subtree_wildcard_subtree_topic(self):
        mqtt.subscribe(self.hass, 'test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic/bier/on', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic/bier/on', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_subtree_wildcard_root_topic(self):
        mqtt.subscribe(self.hass, 'test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_subtree_wildcard_no_match(self):
        mqtt.subscribe(self.hass, 'test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'another-test-topic', 'test-payload')

        self.hass.pool.block_till_done()
        self.assertEqual(0, len(self.calls))
