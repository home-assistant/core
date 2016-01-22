"""
tests.test_component_mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests MQTT component.
"""
from collections import namedtuple
import unittest
from unittest import mock
import socket

import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    EVENT_CALL_SERVICE, ATTR_DOMAIN, ATTR_SERVICE, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP)

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)


class TestMQTT(unittest.TestCase):
    """ Test the MQTT module. """

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


class TestMQTTCallbacks(unittest.TestCase):
    """ Test the MQTT callbacks. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant(1)
        # mock_mqtt_component(self.hass)

        with mock.patch('paho.mqtt.client.Client'):
            mqtt.setup(self.hass, {
                mqtt.DOMAIN: {
                    mqtt.CONF_BROKER: 'mock-broker',
                }
            })
            self.hass.config.components.append(mqtt.DOMAIN)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_receiving_mqtt_message_fires_hass_event(self):
        calls = []

        def record(event):
            calls.append(event)

        self.hass.bus.listen_once(mqtt.EVENT_MQTT_MESSAGE_RECEIVED, record)

        MQTTMessage = namedtuple('MQTTMessage', ['topic', 'qos', 'payload'])
        message = MQTTMessage('test_topic', 1, 'Hello World!'.encode('utf-8'))

        mqtt.MQTT_CLIENT._mqtt_on_message(None, {'hass': self.hass}, message)
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(calls))
        last_event = calls[0]
        self.assertEqual('Hello World!', last_event.data['payload'])
        self.assertEqual(message.topic, last_event.data['topic'])
        self.assertEqual(message.qos, last_event.data['qos'])

    def test_mqtt_failed_connection_results_in_disconnect(self):
        for result_code in range(1, 6):
            mqtt.MQTT_CLIENT._mqttc = mock.MagicMock()
            mqtt.MQTT_CLIENT._mqtt_on_connect(None, {'topics': {}}, 0,
                                              result_code)
            self.assertTrue(mqtt.MQTT_CLIENT._mqttc.disconnect.called)

    def test_mqtt_subscribes_topics_on_connect(self):
        from collections import OrderedDict
        prev_topics = OrderedDict()
        prev_topics['topic/test'] = 1,
        prev_topics['home/sensor'] = 2,
        prev_topics['still/pending'] = None

        mqtt.MQTT_CLIENT.topics = prev_topics
        mqtt.MQTT_CLIENT.progress = {1: 'still/pending'}
        # Return values for subscribe calls (rc, mid)
        mqtt.MQTT_CLIENT._mqttc.subscribe.side_effect = ((0, 2), (0, 3))
        mqtt.MQTT_CLIENT._mqtt_on_connect(None, None, 0, 0)
        self.assertFalse(mqtt.MQTT_CLIENT._mqttc.disconnect.called)

        expected = [(topic, qos) for topic, qos in prev_topics.items()
                    if qos is not None]
        self.assertEqual(
            expected,
            [call[1] for call in mqtt.MQTT_CLIENT._mqttc.subscribe.mock_calls])
        self.assertEqual({
            1: 'still/pending',
            2: 'topic/test',
            3: 'home/sensor',
        }, mqtt.MQTT_CLIENT.progress)

    def test_mqtt_disconnect_tries_no_reconnect_on_stop(self):
        mqtt.MQTT_CLIENT._mqtt_on_disconnect(None, None, 0)
        self.assertFalse(mqtt.MQTT_CLIENT._mqttc.reconnect.called)

    @mock.patch('homeassistant.components.mqtt.time.sleep')
    def test_mqtt_disconnect_tries_reconnect(self, mock_sleep):
        mqtt.MQTT_CLIENT.topics = {
            'test/topic': 1,
            'test/progress': None
        }
        mqtt.MQTT_CLIENT.progress = {
            1: 'test/progress'
        }
        mqtt.MQTT_CLIENT._mqttc.reconnect.side_effect = [1, 1, 1, 0]
        mqtt.MQTT_CLIENT._mqtt_on_disconnect(None, None, 1)
        self.assertTrue(mqtt.MQTT_CLIENT._mqttc.reconnect.called)
        self.assertEqual(4, len(mqtt.MQTT_CLIENT._mqttc.reconnect.mock_calls))
        self.assertEqual([1, 2, 4],
                         [call[1][0] for call in mock_sleep.mock_calls])

        self.assertEqual({'test/topic': 1}, mqtt.MQTT_CLIENT.topics)
        self.assertEqual({}, mqtt.MQTT_CLIENT.progress)
