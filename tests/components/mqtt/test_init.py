"""The tests for the MQTT component."""
from collections import namedtuple
import unittest
from unittest import mock
import socket

import voluptuous as vol

from homeassistant.bootstrap import _setup_component
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    EVENT_CALL_SERVICE, ATTR_DOMAIN, ATTR_SERVICE, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP)

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)


class TestMQTT(unittest.TestCase):
    """Test the MQTT component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant(1)
        mock_mqtt_component(self.hass)
        self.calls = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def record_calls(self, *args):
        """Helper for recording calls."""
        self.calls.append(args)

    def test_client_starts_on_home_assistant_start(self):
        """"Test if client start on HA launch."""
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()
        self.assertTrue(mqtt.MQTT_CLIENT.start.called)

    def test_client_stops_on_home_assistant_start(self):
        """Test if client stops on HA launch."""
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()
        self.hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        self.hass.block_till_done()
        self.assertTrue(mqtt.MQTT_CLIENT.stop.called)

    def test_setup_fails_if_no_connect_broker(self):
        """Test for setup failure if connection to broker is missing."""
        with mock.patch('homeassistant.components.mqtt.MQTT',
                        side_effect=socket.error()):
            self.hass.config.components = []
            assert not _setup_component(self.hass, mqtt.DOMAIN, {
                mqtt.DOMAIN: {
                    mqtt.CONF_BROKER: 'test-broker',
                }
            })

    def test_setup_protocol_validation(self):
        """Test for setup failure if connection to broker is missing."""
        with mock.patch('paho.mqtt.client.Client'):
            self.hass.config.components = []
            assert _setup_component(self.hass, mqtt.DOMAIN, {
                mqtt.DOMAIN: {
                    mqtt.CONF_BROKER: 'test-broker',
                    mqtt.CONF_PROTOCOL: 3.1,
                }
            })

    def test_publish_calls_service(self):
        """Test the publishing of call to services."""
        self.hass.bus.listen_once(EVENT_CALL_SERVICE, self.record_calls)

        mqtt.publish(self.hass, 'test-topic', 'test-payload')

        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))
        self.assertEqual(
                'test-topic',
                self.calls[0][0].data['service_data'][mqtt.ATTR_TOPIC])
        self.assertEqual(
                'test-payload',
                self.calls[0][0].data['service_data'][mqtt.ATTR_PAYLOAD])

    def test_service_call_without_topic_does_not_publish(self):
        """Test the service call if topic is missing."""
        self.hass.bus.fire(EVENT_CALL_SERVICE, {
            ATTR_DOMAIN: mqtt.DOMAIN,
            ATTR_SERVICE: mqtt.SERVICE_PUBLISH
        })
        self.hass.block_till_done()
        self.assertTrue(not mqtt.MQTT_CLIENT.publish.called)

    def test_service_call_with_template_payload_renders_template(self):
        """Test the service call with rendered template.

        If 'payload_template' is provided and 'payload' is not, then render it.
        """
        mqtt.publish_template(self.hass, "test/topic", "{{ 1+1 }}")
        self.hass.block_till_done()
        self.assertTrue(mqtt.MQTT_CLIENT.publish.called)
        self.assertEqual(mqtt.MQTT_CLIENT.publish.call_args[0][1], "2")

    def test_service_call_with_payload_doesnt_render_template(self):
        """Test the service call with unrendered template.

        If both 'payload' and 'payload_template' are provided then fail.
        """
        payload = "not a template"
        payload_template = "a template"
        self.hass.services.call(mqtt.DOMAIN, mqtt.SERVICE_PUBLISH, {
            mqtt.ATTR_TOPIC: "test/topic",
            mqtt.ATTR_PAYLOAD: payload,
            mqtt.ATTR_PAYLOAD_TEMPLATE: payload_template
        }, blocking=True)
        self.assertFalse(mqtt.MQTT_CLIENT.publish.called)

    def test_service_call_with_ascii_qos_retain_flags(self):
        """Test the service call with args that can be misinterpreted.

        Empty payload message and ascii formatted qos and retain flags.
        """
        self.hass.services.call(mqtt.DOMAIN, mqtt.SERVICE_PUBLISH, {
            mqtt.ATTR_TOPIC: "test/topic",
            mqtt.ATTR_PAYLOAD: "",
            mqtt.ATTR_QOS: '2',
            mqtt.ATTR_RETAIN: 'no'
        }, blocking=True)
        self.assertTrue(mqtt.MQTT_CLIENT.publish.called)
        self.assertEqual(mqtt.MQTT_CLIENT.publish.call_args[0][2], 2)
        self.assertFalse(mqtt.MQTT_CLIENT.publish.call_args[0][3])

    def test_subscribe_topic(self):
        """Test the subscription of a topic."""
        unsub = mqtt.subscribe(self.hass, 'test-topic', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

        unsub()

        fire_mqtt_message(self.hass, 'test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_subscribe_topic_not_match(self):
        """Test if subscribed topic is not a match."""
        mqtt.subscribe(self.hass, 'test-topic', self.record_calls)

        fire_mqtt_message(self.hass, 'another-test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_subscribe_topic_level_wildcard(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, 'test-topic/+/on', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic/bier/on', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic/bier/on', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_level_wildcard_no_subtree_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, 'test-topic/+/on', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic/bier', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_subscribe_topic_subtree_wildcard_subtree_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, 'test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic/bier/on', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic/bier/on', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_subtree_wildcard_root_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, 'test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('test-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_subtree_wildcard_no_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, 'test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'another-test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))


class TestMQTTCallbacks(unittest.TestCase):
    """Test the MQTT callbacks."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant(1)
        # mock_mqtt_component(self.hass)

        with mock.patch('paho.mqtt.client.Client'):
            self.hass.config.components = []
            assert _setup_component(self.hass, mqtt.DOMAIN, {
                mqtt.DOMAIN: {
                    mqtt.CONF_BROKER: 'mock-broker',
                }
            })

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_receiving_mqtt_message_fires_hass_event(self):
        """Test if receiving triggers an event."""
        calls = []

        def record(event):
            """Helper to record calls."""
            calls.append(event)

        self.hass.bus.listen_once(mqtt.EVENT_MQTT_MESSAGE_RECEIVED, record)

        MQTTMessage = namedtuple('MQTTMessage', ['topic', 'qos', 'payload'])
        message = MQTTMessage('test_topic', 1, 'Hello World!'.encode('utf-8'))

        mqtt.MQTT_CLIENT._mqtt_on_message(None, {'hass': self.hass}, message)
        self.hass.block_till_done()

        self.assertEqual(1, len(calls))
        last_event = calls[0]
        self.assertEqual('Hello World!', last_event.data['payload'])
        self.assertEqual(message.topic, last_event.data['topic'])
        self.assertEqual(message.qos, last_event.data['qos'])

    def test_mqtt_failed_connection_results_in_disconnect(self):
        """Test if connection failure leads to disconnect."""
        for result_code in range(1, 6):
            mqtt.MQTT_CLIENT._mqttc = mock.MagicMock()
            mqtt.MQTT_CLIENT._mqtt_on_connect(None, {'topics': {}}, 0,
                                              result_code)
            self.assertTrue(mqtt.MQTT_CLIENT._mqttc.disconnect.called)

    def test_mqtt_subscribes_topics_on_connect(self):
        """Test subscription to topic on connect."""
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
        """Test the disconnect tries."""
        mqtt.MQTT_CLIENT._mqtt_on_disconnect(None, None, 0)
        self.assertFalse(mqtt.MQTT_CLIENT._mqttc.reconnect.called)

    @mock.patch('homeassistant.components.mqtt.time.sleep')
    def test_mqtt_disconnect_tries_reconnect(self, mock_sleep):
        """Test the re-connect tries."""
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

    def test_invalid_mqtt_topics(self):
        self.assertRaises(vol.Invalid, mqtt.valid_publish_topic, 'bad+topic')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'bad\0one')
