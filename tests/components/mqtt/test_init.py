"""The tests for the MQTT component."""
import asyncio
import unittest
from unittest import mock
import socket
import ssl

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.setup import async_setup_component
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (EVENT_CALL_SERVICE, ATTR_DOMAIN, ATTR_SERVICE,
                                 EVENT_HOMEASSISTANT_STOP)

from tests.common import (get_test_home_assistant, mock_coro,
                          mock_mqtt_component,
                          threadsafe_coroutine_factory, fire_mqtt_message,
                          async_fire_mqtt_message)


@asyncio.coroutine
def async_mock_mqtt_client(hass, config=None):
    """Mock the MQTT paho client."""
    if config is None:
        config = {mqtt.CONF_BROKER: 'mock-broker'}

    with mock.patch('paho.mqtt.client.Client') as mock_client:
        mock_client().connect.return_value = 0
        mock_client().subscribe.return_value = (0, 0)
        mock_client().unsubscribe.return_value = (0, 0)
        mock_client().publish.return_value = (0, 0)
        result = yield from async_setup_component(hass, mqtt.DOMAIN, {
            mqtt.DOMAIN: config
        })
        assert result
        return mock_client()


mock_mqtt_client = threadsafe_coroutine_factory(async_mock_mqtt_client)


# pylint: disable=invalid-name
class TestMQTTComponent(unittest.TestCase):
    """Test the MQTT component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.calls = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @callback
    def record_calls(self, *args):
        """Helper for recording calls."""
        self.calls.append(args)

    def aiohttp_client_stops_on_home_assistant_start(self):
        """Test if client stops on HA stop."""
        self.hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        self.hass.block_till_done()
        self.assertTrue(self.hass.data['mqtt'].async_disconnect.called)

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
        self.assertTrue(not self.hass.data['mqtt'].async_publish.called)

    def test_service_call_with_template_payload_renders_template(self):
        """Test the service call with rendered template.

        If 'payload_template' is provided and 'payload' is not, then render it.
        """
        mqtt.publish_template(self.hass, "test/topic", "{{ 1+1 }}")
        self.hass.block_till_done()
        self.assertTrue(self.hass.data['mqtt'].async_publish.called)
        self.assertEqual(
            self.hass.data['mqtt'].async_publish.call_args[0][1], "2")

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
        self.assertFalse(self.hass.data['mqtt'].async_publish.called)

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
        self.assertTrue(self.hass.data['mqtt'].async_publish.called)
        self.assertEqual(
            self.hass.data['mqtt'].async_publish.call_args[0][2], 2)
        self.assertFalse(self.hass.data['mqtt'].async_publish.call_args[0][3])

    def test_validate_topic(self):
        """Test topic name/filter validation."""
        # Invalid UTF-8, must not contain U+D800 to U+DFFF.
        self.assertRaises(vol.Invalid, mqtt.valid_topic, '\ud800')
        self.assertRaises(vol.Invalid, mqtt.valid_topic, '\udfff')
        # Topic MUST NOT be empty
        self.assertRaises(vol.Invalid, mqtt.valid_topic, '')
        # Topic MUST NOT be longer than 65535 encoded bytes.
        self.assertRaises(vol.Invalid, mqtt.valid_topic, 'ü' * 32768)
        # UTF-8 MUST NOT include null character
        self.assertRaises(vol.Invalid, mqtt.valid_topic, 'bad\0one')

        # Topics "SHOULD NOT" include these special characters
        # (not MUST NOT, RFC2119). The receiver MAY close the connection.
        mqtt.valid_topic('\u0001')
        mqtt.valid_topic('\u001F')
        mqtt.valid_topic('\u009F')
        mqtt.valid_topic('\u009F')
        mqtt.valid_topic('\uffff')

    def test_validate_subscribe_topic(self):
        """Test invalid subscribe topics."""
        mqtt.valid_subscribe_topic('#')
        mqtt.valid_subscribe_topic('sport/#')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'sport/#/')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'foo/bar#')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'foo/#/bar')

        mqtt.valid_subscribe_topic('+')
        mqtt.valid_subscribe_topic('+/tennis/#')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'sport+')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'sport+/')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'sport/+1')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'sport/+#')
        self.assertRaises(vol.Invalid, mqtt.valid_subscribe_topic, 'bad+topic')
        mqtt.valid_subscribe_topic('sport/+/player1')
        mqtt.valid_subscribe_topic('/finance')
        mqtt.valid_subscribe_topic('+/+')
        mqtt.valid_subscribe_topic('$SYS/#')

    def test_validate_publish_topic(self):
        """Test invalid publish topics."""
        self.assertRaises(vol.Invalid, mqtt.valid_publish_topic, 'pub+')
        self.assertRaises(vol.Invalid, mqtt.valid_publish_topic, 'pub/+')
        self.assertRaises(vol.Invalid, mqtt.valid_publish_topic, '1#')
        self.assertRaises(vol.Invalid, mqtt.valid_publish_topic, 'bad+topic')
        mqtt.valid_publish_topic('//')

        # Topic names beginning with $ SHOULD NOT be used, but can
        mqtt.valid_publish_topic('$SYS/')


# pylint: disable=invalid-name
class TestMQTTCallbacks(unittest.TestCase):
    """Test the MQTT callbacks."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_client(self.hass)
        self.calls = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @callback
    def record_calls(self, *args):
        """Helper for recording calls."""
        self.calls.append(args)

    def aiohttp_client_starts_on_home_assistant_mqtt_setup(self):
        """Test if client is connected after mqtt init on bootstrap."""
        self.assertEqual(self.hass.data['mqtt']._mqttc.connect.call_count, 1)

    def test_receiving_non_utf8_message_gets_logged(self):
        """Test receiving a non utf8 encoded message."""
        mqtt.subscribe(self.hass, 'test-topic', self.record_calls)

        with self.assertLogs(level='WARNING') as test_handle:
            fire_mqtt_message(self.hass, 'test-topic', b'\x9a')

            self.hass.block_till_done()
            self.assertIn(
                "WARNING:homeassistant.components.mqtt:Can't decode payload "
                "b'\\x9a' on test-topic with encoding utf-8",
                test_handle.output[0])

    def test_all_subscriptions_run_when_decode_fails(self):
        """Test all other subscriptions still run when decode fails for one."""
        mqtt.subscribe(self.hass, 'test-topic', self.record_calls,
                       encoding='ascii')
        mqtt.subscribe(self.hass, 'test-topic', self.record_calls)

        fire_mqtt_message(self.hass, 'test-topic', '°C')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

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

    def test_subscribe_topic_level_wildcard_and_wildcard_root_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, '+/test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'hi/test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('hi/test-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_level_wildcard_and_wildcard_subtree_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, '+/test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'hi/test-topic/here-iam', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('hi/test-topic/here-iam', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_level_wildcard_and_wildcard_level_no_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, '+/test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'hi/here-iam/test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_subscribe_topic_level_wildcard_and_wildcard_no_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, '+/test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, 'hi/another-test-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_subscribe_topic_sys_root(self):
        """Test the subscription of $ root topics."""
        mqtt.subscribe(self.hass, '$test-topic/subtree/on', self.record_calls)

        fire_mqtt_message(self.hass, '$test-topic/subtree/on', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('$test-topic/subtree/on', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_sys_root_and_wildcard_topic(self):
        """Test the subscription of $ root and wildcard topics."""
        mqtt.subscribe(self.hass, '$test-topic/#', self.record_calls)

        fire_mqtt_message(self.hass, '$test-topic/some-topic', 'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('$test-topic/some-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_topic_sys_root_and_wildcard_subtree_topic(self):
        """Test the subscription of $ root and wildcard subtree topics."""
        mqtt.subscribe(self.hass, '$test-topic/subtree/#', self.record_calls)

        fire_mqtt_message(self.hass, '$test-topic/subtree/some-topic',
                          'test-payload')

        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual('$test-topic/subtree/some-topic', self.calls[0][0])
        self.assertEqual('test-payload', self.calls[0][1])

    def test_subscribe_special_characters(self):
        """Test the subscription to topics with special characters."""
        topic = '/test-topic/$(.)[^]{-}'
        payload = 'p4y.l[]a|> ?'

        mqtt.subscribe(self.hass, topic, self.record_calls)

        fire_mqtt_message(self.hass, topic, payload)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(topic, self.calls[0][0])
        self.assertEqual(payload, self.calls[0][1])

    def test_mqtt_failed_connection_results_in_disconnect(self):
        """Test if connection failure leads to disconnect."""
        for result_code in range(1, 6):
            self.hass.data['mqtt']._mqttc = mock.MagicMock()
            self.hass.data['mqtt']._mqtt_on_connect(
                None, {'topics': {}}, 0, result_code)
            self.assertTrue(self.hass.data['mqtt']._mqttc.disconnect.called)

    def test_mqtt_disconnect_tries_no_reconnect_on_stop(self):
        """Test the disconnect tries."""
        self.hass.data['mqtt']._mqtt_on_disconnect(None, None, 0)
        self.assertFalse(self.hass.data['mqtt']._mqttc.reconnect.called)

    @mock.patch('homeassistant.components.mqtt.time.sleep')
    def test_mqtt_disconnect_tries_reconnect(self, mock_sleep):
        """Test the re-connect tries."""
        self.hass.data['mqtt'].subscriptions = [
            mqtt.Subscription('test/progress', None, 0),
            mqtt.Subscription('test/progress', None, 1),
            mqtt.Subscription('test/topic', None, 2),
        ]
        self.hass.data['mqtt']._mqttc.reconnect.side_effect = [1, 1, 1, 0]
        self.hass.data['mqtt']._mqtt_on_disconnect(None, None, 1)
        self.assertTrue(self.hass.data['mqtt']._mqttc.reconnect.called)
        self.assertEqual(
            4, len(self.hass.data['mqtt']._mqttc.reconnect.mock_calls))
        self.assertEqual([1, 2, 4],
                         [call[1][0] for call in mock_sleep.mock_calls])

    def test_retained_message_on_subscribe_received(self):
        """Test every subscriber receives retained message on subscribe."""
        def side_effect(*args):
            async_fire_mqtt_message(self.hass, 'test/state', 'online')
            return 0, 0

        self.hass.data['mqtt']._mqttc.subscribe.side_effect = side_effect

        calls_a = mock.MagicMock()
        mqtt.subscribe(self.hass, 'test/state', calls_a)
        self.hass.block_till_done()
        self.assertTrue(calls_a.called)

        calls_b = mock.MagicMock()
        mqtt.subscribe(self.hass, 'test/state', calls_b)
        self.hass.block_till_done()
        self.assertTrue(calls_b.called)

    def test_not_calling_unsubscribe_with_active_subscribers(self):
        """Test not calling unsubscribe() when other subscribers are active."""
        unsub = mqtt.subscribe(self.hass, 'test/state', None)
        mqtt.subscribe(self.hass, 'test/state', None)
        self.hass.block_till_done()
        self.assertTrue(self.hass.data['mqtt']._mqttc.subscribe.called)

        unsub()
        self.hass.block_till_done()
        self.assertFalse(self.hass.data['mqtt']._mqttc.unsubscribe.called)

    def test_restore_subscriptions_on_reconnect(self):
        """Test subscriptions are restored on reconnect."""
        mqtt.subscribe(self.hass, 'test/state', None)
        self.hass.block_till_done()
        self.assertEqual(self.hass.data['mqtt']._mqttc.subscribe.call_count, 1)

        self.hass.data['mqtt']._mqtt_on_disconnect(None, None, 0)
        self.hass.data['mqtt']._mqtt_on_connect(None, None, None, 0)
        self.hass.block_till_done()
        self.assertEqual(self.hass.data['mqtt']._mqttc.subscribe.call_count, 2)

    def test_restore_all_active_subscriptions_on_reconnect(self):
        """Test active subscriptions are restored correctly on reconnect."""
        self.hass.data['mqtt']._mqttc.subscribe.side_effect = (
            (0, 1), (0, 2), (0, 3), (0, 4)
        )

        unsub = mqtt.subscribe(self.hass, 'test/state', None, qos=2)
        mqtt.subscribe(self.hass, 'test/state', None)
        mqtt.subscribe(self.hass, 'test/state', None, qos=1)
        self.hass.block_till_done()

        expected = [
            mock.call('test/state', 2),
            mock.call('test/state', 0),
            mock.call('test/state', 1)
        ]
        self.assertEqual(self.hass.data['mqtt']._mqttc.subscribe.mock_calls,
                         expected)

        unsub()
        self.hass.block_till_done()
        self.assertEqual(self.hass.data['mqtt']._mqttc.unsubscribe.call_count,
                         0)

        self.hass.data['mqtt']._mqtt_on_disconnect(None, None, 0)
        self.hass.data['mqtt']._mqtt_on_connect(None, None, None, 0)
        self.hass.block_till_done()

        expected.append(mock.call('test/state', 1))
        self.assertEqual(self.hass.data['mqtt']._mqttc.subscribe.mock_calls,
                         expected)


@asyncio.coroutine
def test_setup_embedded_starts_with_no_config(hass):
    """Test setting up embedded server with no config."""
    client_config = ('localhost', 1883, 'user', 'pass', None, '3.1.1')

    with mock.patch('homeassistant.components.mqtt.server.async_start',
                    return_value=mock_coro(
                        return_value=(True, client_config))
                    ) as _start:
        yield from async_mock_mqtt_client(hass, {})
        assert _start.call_count == 1


@asyncio.coroutine
def test_setup_embedded_with_embedded(hass):
    """Test setting up embedded server with no config."""
    client_config = ('localhost', 1883, 'user', 'pass', None, '3.1.1')

    with mock.patch('homeassistant.components.mqtt.server.async_start',
                    return_value=mock_coro(
                        return_value=(True, client_config))
                    ) as _start:
        _start.return_value = mock_coro(return_value=(True, client_config))
        yield from async_mock_mqtt_client(hass, {'embedded': None})
        assert _start.call_count == 1


@asyncio.coroutine
def test_setup_fails_if_no_connect_broker(hass):
    """Test for setup failure if connection to broker is missing."""
    test_broker_cfg = {mqtt.DOMAIN: {mqtt.CONF_BROKER: 'test-broker'}}

    with mock.patch('homeassistant.components.mqtt.MQTT',
                    side_effect=socket.error()):
        result = yield from async_setup_component(hass, mqtt.DOMAIN,
                                                  test_broker_cfg)
        assert not result

    with mock.patch('paho.mqtt.client.Client') as mock_client:
        mock_client().connect = lambda *args: 1
        result = yield from async_setup_component(hass, mqtt.DOMAIN,
                                                  test_broker_cfg)
        assert not result


@asyncio.coroutine
def test_setup_uses_certificate_on_certificate_set_to_auto(hass):
    """Test setup uses bundled certs when certificate is set to auto."""
    test_broker_cfg = {mqtt.DOMAIN: {mqtt.CONF_BROKER: 'test-broker',
                                     'certificate': 'auto'}}

    with mock.patch('homeassistant.components.mqtt.MQTT') as mock_MQTT:
        yield from async_setup_component(hass, mqtt.DOMAIN, test_broker_cfg)

    assert mock_MQTT.called

    import requests.certs
    expectedCertificate = requests.certs.where()
    assert mock_MQTT.mock_calls[0][1][7] == expectedCertificate


@asyncio.coroutine
def test_setup_does_not_use_certificate_on_mqtts_port(hass):
    """Test setup doesn't use bundled certs when certificate is not set."""
    test_broker_cfg = {mqtt.DOMAIN: {mqtt.CONF_BROKER: 'test-broker',
                                     'port': 8883}}

    with mock.patch('homeassistant.components.mqtt.MQTT') as mock_MQTT:
        yield from async_setup_component(hass, mqtt.DOMAIN, test_broker_cfg)

    assert mock_MQTT.called
    assert mock_MQTT.mock_calls[0][1][2] == 8883

    import requests.certs
    mqttsCertificateBundle = requests.certs.where()
    assert mock_MQTT.mock_calls[0][1][7] != mqttsCertificateBundle


@asyncio.coroutine
def test_setup_without_tls_config_uses_tlsv1_under_python36(hass):
    """Test setup defaults to TLSv1 under python3.6."""
    test_broker_cfg = {mqtt.DOMAIN: {mqtt.CONF_BROKER: 'test-broker'}}

    with mock.patch('homeassistant.components.mqtt.MQTT') as mock_MQTT:
        yield from async_setup_component(hass, mqtt.DOMAIN, test_broker_cfg)

    assert mock_MQTT.called

    import sys
    if sys.hexversion >= 0x03060000:
        expectedTlsVersion = ssl.PROTOCOL_TLS  # pylint: disable=no-member
    else:
        expectedTlsVersion = ssl.PROTOCOL_TLSv1

    assert mock_MQTT.mock_calls[0][1][14] == expectedTlsVersion


@asyncio.coroutine
def test_setup_with_tls_config_uses_tls_version1_2(hass):
    """Test setup uses specified TLS version."""
    test_broker_cfg = {mqtt.DOMAIN: {mqtt.CONF_BROKER: 'test-broker',
                                     'tls_version': '1.2'}}

    with mock.patch('homeassistant.components.mqtt.MQTT') as mock_MQTT:
        yield from async_setup_component(hass, mqtt.DOMAIN, test_broker_cfg)

    assert mock_MQTT.called

    assert mock_MQTT.mock_calls[0][1][14] == ssl.PROTOCOL_TLSv1_2


@asyncio.coroutine
def test_setup_with_tls_config_of_v1_under_python36_only_uses_v1(hass):
    """Test setup uses TLSv1.0 if explicitly chosen."""
    test_broker_cfg = {mqtt.DOMAIN: {mqtt.CONF_BROKER: 'test-broker',
                                     'tls_version': '1.0'}}

    with mock.patch('homeassistant.components.mqtt.MQTT') as mock_MQTT:
        yield from async_setup_component(hass, mqtt.DOMAIN, test_broker_cfg)

    assert mock_MQTT.called
    assert mock_MQTT.mock_calls[0][1][14] == ssl.PROTOCOL_TLSv1


@asyncio.coroutine
def test_birth_message(hass):
    """Test sending birth message."""
    mqtt_client = yield from async_mock_mqtt_client(hass, {
        mqtt.CONF_BROKER: 'mock-broker',
        mqtt.CONF_BIRTH_MESSAGE: {mqtt.ATTR_TOPIC: 'birth',
                                  mqtt.ATTR_PAYLOAD: 'birth'}
    })
    calls = []
    mqtt_client.publish.side_effect = lambda *args: calls.append(args)
    hass.data['mqtt']._mqtt_on_connect(None, None, 0, 0)
    yield from hass.async_block_till_done()
    assert calls[-1] == ('birth', 'birth', 0, False)


@asyncio.coroutine
def test_mqtt_subscribes_topics_on_connect(hass):
    """Test subscription to topic on connect."""
    mqtt_client = yield from async_mock_mqtt_client(hass)

    hass.data['mqtt'].subscriptions = [
        mqtt.Subscription('topic/test', None),
        mqtt.Subscription('home/sensor', None, 2),
        mqtt.Subscription('still/pending', None),
        mqtt.Subscription('still/pending', None, 1),
    ]

    hass.add_job = mock.MagicMock()
    hass.data['mqtt']._mqtt_on_connect(None, None, 0, 0)

    yield from hass.async_block_till_done()

    assert mqtt_client.disconnect.call_count == 0

    expected = {
        'topic/test': 0,
        'home/sensor': 2,
        'still/pending': 1
    }
    calls = {call[1][1]: call[1][2] for call in hass.add_job.mock_calls}
    assert calls == expected
