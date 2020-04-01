"""The tests for the MQTT component."""
from datetime import timedelta
import json
import ssl
import unittest
from unittest import mock

import pytest
import voluptuous as vol

from homeassistant.components import mqtt, websocket_api
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_mqtt_component,
    fire_mqtt_message,
    get_test_home_assistant,
    mock_coro,
    mock_device_registry,
    mock_mqtt_component,
    mock_registry,
    threadsafe_coroutine_factory,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def mock_MQTT():
    """Make sure connection is established."""
    with mock.patch("homeassistant.components.mqtt.MQTT") as mock_MQTT:
        mock_MQTT.return_value.async_connect.return_value = mock_coro(True)
        yield mock_MQTT


async def async_mock_mqtt_client(hass, config=None):
    """Mock the MQTT paho client."""
    if config is None:
        config = {mqtt.CONF_BROKER: "mock-broker"}

    with mock.patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect.return_value = 0
        mock_client().subscribe.return_value = (0, 0)
        mock_client().unsubscribe.return_value = (0, 0)
        mock_client().publish.return_value = (0, 0)
        result = await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: config})
        assert result
        await hass.async_block_till_done()
        return mock_client()


mock_mqtt_client = threadsafe_coroutine_factory(async_mock_mqtt_client)


# pylint: disable=invalid-name
class TestMQTTComponent(unittest.TestCase):
    """Test the MQTT component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.calls = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @callback
    def record_calls(self, *args):
        """Record calls."""
        self.calls.append(args)

    def aiohttp_client_stops_on_home_assistant_start(self):
        """Test if client stops on HA stop."""
        self.hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        self.hass.block_till_done()
        assert self.hass.data["mqtt"].async_disconnect.called

    def test_publish_calls_service(self):
        """Test the publishing of call to services."""
        self.hass.bus.listen_once(EVENT_CALL_SERVICE, self.record_calls)

        mqtt.publish(self.hass, "test-topic", "test-payload")

        self.hass.block_till_done()

        assert len(self.calls) == 1
        assert self.calls[0][0].data["service_data"][mqtt.ATTR_TOPIC] == "test-topic"
        assert (
            self.calls[0][0].data["service_data"][mqtt.ATTR_PAYLOAD] == "test-payload"
        )

    def test_service_call_without_topic_does_not_publish(self):
        """Test the service call if topic is missing."""
        self.hass.bus.fire(
            EVENT_CALL_SERVICE,
            {ATTR_DOMAIN: mqtt.DOMAIN, ATTR_SERVICE: mqtt.SERVICE_PUBLISH},
        )
        self.hass.block_till_done()
        assert not self.hass.data["mqtt"].async_publish.called

    def test_service_call_with_template_payload_renders_template(self):
        """Test the service call with rendered template.

        If 'payload_template' is provided and 'payload' is not, then render it.
        """
        mqtt.publish_template(self.hass, "test/topic", "{{ 1+1 }}")
        self.hass.block_till_done()
        assert self.hass.data["mqtt"].async_publish.called
        assert self.hass.data["mqtt"].async_publish.call_args[0][1] == "2"

    def test_service_call_with_payload_doesnt_render_template(self):
        """Test the service call with unrendered template.

        If both 'payload' and 'payload_template' are provided then fail.
        """
        payload = "not a template"
        payload_template = "a template"
        with pytest.raises(vol.Invalid):
            self.hass.services.call(
                mqtt.DOMAIN,
                mqtt.SERVICE_PUBLISH,
                {
                    mqtt.ATTR_TOPIC: "test/topic",
                    mqtt.ATTR_PAYLOAD: payload,
                    mqtt.ATTR_PAYLOAD_TEMPLATE: payload_template,
                },
                blocking=True,
            )
        assert not self.hass.data["mqtt"].async_publish.called

    def test_service_call_with_ascii_qos_retain_flags(self):
        """Test the service call with args that can be misinterpreted.

        Empty payload message and ascii formatted qos and retain flags.
        """
        self.hass.services.call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: "test/topic",
                mqtt.ATTR_PAYLOAD: "",
                mqtt.ATTR_QOS: "2",
                mqtt.ATTR_RETAIN: "no",
            },
            blocking=True,
        )
        assert self.hass.data["mqtt"].async_publish.called
        assert self.hass.data["mqtt"].async_publish.call_args[0][2] == 2
        assert not self.hass.data["mqtt"].async_publish.call_args[0][3]

    def test_validate_topic(self):
        """Test topic name/filter validation."""
        # Invalid UTF-8, must not contain U+D800 to U+DFFF.
        with pytest.raises(vol.Invalid):
            mqtt.valid_topic("\ud800")
        with pytest.raises(vol.Invalid):
            mqtt.valid_topic("\udfff")
        # Topic MUST NOT be empty
        with pytest.raises(vol.Invalid):
            mqtt.valid_topic("")
        # Topic MUST NOT be longer than 65535 encoded bytes.
        with pytest.raises(vol.Invalid):
            mqtt.valid_topic("ü" * 32768)
        # UTF-8 MUST NOT include null character
        with pytest.raises(vol.Invalid):
            mqtt.valid_topic("bad\0one")

        # Topics "SHOULD NOT" include these special characters
        # (not MUST NOT, RFC2119). The receiver MAY close the connection.
        mqtt.valid_topic("\u0001")
        mqtt.valid_topic("\u001F")
        mqtt.valid_topic("\u009F")
        mqtt.valid_topic("\u009F")
        mqtt.valid_topic("\uffff")

    def test_validate_subscribe_topic(self):
        """Test invalid subscribe topics."""
        mqtt.valid_subscribe_topic("#")
        mqtt.valid_subscribe_topic("sport/#")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("sport/#/")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("foo/bar#")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("foo/#/bar")

        mqtt.valid_subscribe_topic("+")
        mqtt.valid_subscribe_topic("+/tennis/#")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("sport+")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("sport+/")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("sport/+1")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("sport/+#")
        with pytest.raises(vol.Invalid):
            mqtt.valid_subscribe_topic("bad+topic")
        mqtt.valid_subscribe_topic("sport/+/player1")
        mqtt.valid_subscribe_topic("/finance")
        mqtt.valid_subscribe_topic("+/+")
        mqtt.valid_subscribe_topic("$SYS/#")

    def test_validate_publish_topic(self):
        """Test invalid publish topics."""
        with pytest.raises(vol.Invalid):
            mqtt.valid_publish_topic("pub+")
        with pytest.raises(vol.Invalid):
            mqtt.valid_publish_topic("pub/+")
        with pytest.raises(vol.Invalid):
            mqtt.valid_publish_topic("1#")
        with pytest.raises(vol.Invalid):
            mqtt.valid_publish_topic("bad+topic")
        mqtt.valid_publish_topic("//")

        # Topic names beginning with $ SHOULD NOT be used, but can
        mqtt.valid_publish_topic("$SYS/")

    def test_entity_device_info_schema(self):
        """Test MQTT entity device info validation."""
        # just identifier
        mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA({"identifiers": ["abcd"]})
        mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA({"identifiers": "abcd"})
        # just connection
        mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA(
            {"connections": [["mac", "02:5b:26:a8:dc:12"]]}
        )
        # full device info
        mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA(
            {
                "identifiers": ["helloworld", "hello"],
                "connections": [["mac", "02:5b:26:a8:dc:12"], ["zigbee", "zigbee_id"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
            }
        )
        # full device info with via_device
        mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA(
            {
                "identifiers": ["helloworld", "hello"],
                "connections": [["mac", "02:5b:26:a8:dc:12"], ["zigbee", "zigbee_id"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
                "via_device": "test-hub",
            }
        )
        # no identifiers
        with pytest.raises(vol.Invalid):
            mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA(
                {
                    "manufacturer": "Whatever",
                    "name": "Beer",
                    "model": "Glass",
                    "sw_version": "0.1-beta",
                }
            )
        # empty identifiers
        with pytest.raises(vol.Invalid):
            mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA(
                {"identifiers": [], "connections": [], "name": "Beer"}
            )


# pylint: disable=invalid-name
class TestMQTTCallbacks(unittest.TestCase):
    """Test the MQTT callbacks."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_client(self.hass)
        self.calls = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @callback
    def record_calls(self, *args):
        """Record calls."""
        self.calls.append(args)

    def aiohttp_client_starts_on_home_assistant_mqtt_setup(self):
        """Test if client is connected after mqtt init on bootstrap."""
        assert self.hass.data["mqtt"]._mqttc.connect.call_count == 1

    def test_receiving_non_utf8_message_gets_logged(self):
        """Test receiving a non utf8 encoded message."""
        mqtt.subscribe(self.hass, "test-topic", self.record_calls)

        with self.assertLogs(level="WARNING") as test_handle:
            fire_mqtt_message(self.hass, "test-topic", b"\x9a")

            self.hass.block_till_done()
            assert (
                "WARNING:homeassistant.components.mqtt:Can't decode payload "
                "b'\\x9a' on test-topic with encoding utf-8" in test_handle.output[0]
            )

    def test_all_subscriptions_run_when_decode_fails(self):
        """Test all other subscriptions still run when decode fails for one."""
        mqtt.subscribe(self.hass, "test-topic", self.record_calls, encoding="ascii")
        mqtt.subscribe(self.hass, "test-topic", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic", "°C")

        self.hass.block_till_done()
        assert len(self.calls) == 1

    def test_subscribe_topic(self):
        """Test the subscription of a topic."""
        unsub = mqtt.subscribe(self.hass, "test-topic", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "test-topic"
        assert self.calls[0][0].payload == "test-payload"

        unsub()

        fire_mqtt_message(self.hass, "test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1

    def test_subscribe_topic_not_match(self):
        """Test if subscribed topic is not a match."""
        mqtt.subscribe(self.hass, "test-topic", self.record_calls)

        fire_mqtt_message(self.hass, "another-test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_subscribe_topic_level_wildcard(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "test-topic/+/on", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic/bier/on", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "test-topic/bier/on"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_level_wildcard_no_subtree_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "test-topic/+/on", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic/bier", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_subscribe_topic_level_wildcard_root_topic_no_subtree_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic-123", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_subscribe_topic_subtree_wildcard_subtree_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic/bier/on", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "test-topic/bier/on"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_subtree_wildcard_root_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "test-topic"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_subtree_wildcard_no_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "another-test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_subscribe_topic_level_wildcard_and_wildcard_root_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "+/test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "hi/test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "hi/test-topic"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_level_wildcard_and_wildcard_subtree_topic(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "+/test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "hi/test-topic/here-iam", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "hi/test-topic/here-iam"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_level_wildcard_and_wildcard_level_no_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "+/test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "hi/here-iam/test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_subscribe_topic_level_wildcard_and_wildcard_no_match(self):
        """Test the subscription of wildcard topics."""
        mqtt.subscribe(self.hass, "+/test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "hi/another-test-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_subscribe_topic_sys_root(self):
        """Test the subscription of $ root topics."""
        mqtt.subscribe(self.hass, "$test-topic/subtree/on", self.record_calls)

        fire_mqtt_message(self.hass, "$test-topic/subtree/on", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "$test-topic/subtree/on"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_sys_root_and_wildcard_topic(self):
        """Test the subscription of $ root and wildcard topics."""
        mqtt.subscribe(self.hass, "$test-topic/#", self.record_calls)

        fire_mqtt_message(self.hass, "$test-topic/some-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "$test-topic/some-topic"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_topic_sys_root_and_wildcard_subtree_topic(self):
        """Test the subscription of $ root and wildcard subtree topics."""
        mqtt.subscribe(self.hass, "$test-topic/subtree/#", self.record_calls)

        fire_mqtt_message(self.hass, "$test-topic/subtree/some-topic", "test-payload")

        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == "$test-topic/subtree/some-topic"
        assert self.calls[0][0].payload == "test-payload"

    def test_subscribe_special_characters(self):
        """Test the subscription to topics with special characters."""
        topic = "/test-topic/$(.)[^]{-}"
        payload = "p4y.l[]a|> ?"

        mqtt.subscribe(self.hass, topic, self.record_calls)

        fire_mqtt_message(self.hass, topic, payload)
        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0][0].topic == topic
        assert self.calls[0][0].payload == payload

    def test_mqtt_failed_connection_results_in_disconnect(self):
        """Test if connection failure leads to disconnect."""
        for result_code in range(1, 6):
            self.hass.data["mqtt"]._mqttc = mock.MagicMock()
            self.hass.data["mqtt"]._mqtt_on_connect(
                None, {"topics": {}}, 0, result_code
            )
            assert self.hass.data["mqtt"]._mqttc.disconnect.called

    def test_mqtt_disconnect_tries_no_reconnect_on_stop(self):
        """Test the disconnect tries."""
        self.hass.data["mqtt"]._mqtt_on_disconnect(None, None, 0)
        assert not self.hass.data["mqtt"]._mqttc.reconnect.called

    @mock.patch("homeassistant.components.mqtt.time.sleep")
    def test_mqtt_disconnect_tries_reconnect(self, mock_sleep):
        """Test the re-connect tries."""
        self.hass.data["mqtt"].subscriptions = [
            mqtt.Subscription("test/progress", None, 0),
            mqtt.Subscription("test/progress", None, 1),
            mqtt.Subscription("test/topic", None, 2),
        ]
        self.hass.data["mqtt"]._mqttc.reconnect.side_effect = [1, 1, 1, 0]
        self.hass.data["mqtt"]._mqtt_on_disconnect(None, None, 1)
        assert self.hass.data["mqtt"]._mqttc.reconnect.called
        assert len(self.hass.data["mqtt"]._mqttc.reconnect.mock_calls) == 4
        assert [call[1][0] for call in mock_sleep.mock_calls] == [1, 2, 4]

    def test_retained_message_on_subscribe_received(self):
        """Test every subscriber receives retained message on subscribe."""

        def side_effect(*args):
            async_fire_mqtt_message(self.hass, "test/state", "online")
            return 0, 0

        self.hass.data["mqtt"]._mqttc.subscribe.side_effect = side_effect

        calls_a = mock.MagicMock()
        mqtt.subscribe(self.hass, "test/state", calls_a)
        self.hass.block_till_done()
        assert calls_a.called

        calls_b = mock.MagicMock()
        mqtt.subscribe(self.hass, "test/state", calls_b)
        self.hass.block_till_done()
        assert calls_b.called

    def test_not_calling_unsubscribe_with_active_subscribers(self):
        """Test not calling unsubscribe() when other subscribers are active."""
        unsub = mqtt.subscribe(self.hass, "test/state", None)
        mqtt.subscribe(self.hass, "test/state", None)
        self.hass.block_till_done()
        assert self.hass.data["mqtt"]._mqttc.subscribe.called

        unsub()
        self.hass.block_till_done()
        assert not self.hass.data["mqtt"]._mqttc.unsubscribe.called

    def test_restore_subscriptions_on_reconnect(self):
        """Test subscriptions are restored on reconnect."""
        mqtt.subscribe(self.hass, "test/state", None)
        self.hass.block_till_done()
        assert self.hass.data["mqtt"]._mqttc.subscribe.call_count == 1

        self.hass.data["mqtt"]._mqtt_on_disconnect(None, None, 0)
        self.hass.data["mqtt"]._mqtt_on_connect(None, None, None, 0)
        self.hass.block_till_done()
        assert self.hass.data["mqtt"]._mqttc.subscribe.call_count == 2

    def test_restore_all_active_subscriptions_on_reconnect(self):
        """Test active subscriptions are restored correctly on reconnect."""
        self.hass.data["mqtt"]._mqttc.subscribe.side_effect = (
            (0, 1),
            (0, 2),
            (0, 3),
            (0, 4),
        )

        unsub = mqtt.subscribe(self.hass, "test/state", None, qos=2)
        mqtt.subscribe(self.hass, "test/state", None)
        mqtt.subscribe(self.hass, "test/state", None, qos=1)
        self.hass.block_till_done()

        expected = [
            mock.call("test/state", 2),
            mock.call("test/state", 0),
            mock.call("test/state", 1),
        ]
        assert self.hass.data["mqtt"]._mqttc.subscribe.mock_calls == expected

        unsub()
        self.hass.block_till_done()
        assert self.hass.data["mqtt"]._mqttc.unsubscribe.call_count == 0

        self.hass.data["mqtt"]._mqtt_on_disconnect(None, None, 0)
        self.hass.data["mqtt"]._mqtt_on_connect(None, None, None, 0)
        self.hass.block_till_done()

        expected.append(mock.call("test/state", 1))
        assert self.hass.data["mqtt"]._mqttc.subscribe.mock_calls == expected


async def test_setup_embedded_starts_with_no_config(hass):
    """Test setting up embedded server with no config."""
    client_config = ("localhost", 1883, "user", "pass", None, "3.1.1")

    with mock.patch(
        "homeassistant.components.mqtt.server.async_start",
        return_value=mock_coro(return_value=(True, client_config)),
    ) as _start:
        await async_mock_mqtt_client(hass, {})
        assert _start.call_count == 1


async def test_setup_embedded_with_embedded(hass):
    """Test setting up embedded server with no config."""
    client_config = ("localhost", 1883, "user", "pass", None, "3.1.1")

    with mock.patch(
        "homeassistant.components.mqtt.server.async_start",
        return_value=mock_coro(return_value=(True, client_config)),
    ) as _start:
        _start.return_value = mock_coro(return_value=(True, client_config))
        await async_mock_mqtt_client(hass, {"embedded": None})
        assert _start.call_count == 1


async def test_setup_fails_if_no_connect_broker(hass):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})

    with mock.patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = lambda *args: 1
        assert not await mqtt.async_setup_entry(hass, entry)


async def test_setup_raises_ConfigEntryNotReady_if_no_connect_broker(hass):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})

    with mock.patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = mock.Mock(side_effect=OSError("Connection error"))
        with pytest.raises(ConfigEntryNotReady):
            await mqtt.async_setup_entry(hass, entry)


async def test_setup_uses_certificate_on_certificate_set_to_auto(hass, mock_MQTT):
    """Test setup uses bundled certs when certificate is set to auto."""
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={mqtt.CONF_BROKER: "test-broker", "certificate": "auto"},
    )

    assert await mqtt.async_setup_entry(hass, entry)

    assert mock_MQTT.called

    import requests.certs

    expectedCertificate = requests.certs.where()
    assert mock_MQTT.mock_calls[0][2]["certificate"] == expectedCertificate


async def test_setup_does_not_use_certificate_on_mqtts_port(hass, mock_MQTT):
    """Test setup doesn't use bundled certs when ssl set."""
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker", "port": 8883}
    )

    assert await mqtt.async_setup_entry(hass, entry)

    assert mock_MQTT.called
    assert mock_MQTT.mock_calls[0][2]["port"] == 8883

    import requests.certs

    mqttsCertificateBundle = requests.certs.where()
    assert mock_MQTT.mock_calls[0][2]["port"] != mqttsCertificateBundle


async def test_setup_without_tls_config_uses_tlsv1_under_python36(hass, mock_MQTT):
    """Test setup defaults to TLSv1 under python3.6."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})

    assert await mqtt.async_setup_entry(hass, entry)

    assert mock_MQTT.called

    import sys

    if sys.hexversion >= 0x03060000:
        expectedTlsVersion = ssl.PROTOCOL_TLS  # pylint: disable=no-member
    else:
        expectedTlsVersion = ssl.PROTOCOL_TLSv1

    assert mock_MQTT.mock_calls[0][2]["tls_version"] == expectedTlsVersion


async def test_setup_with_tls_config_uses_tls_version1_2(hass, mock_MQTT):
    """Test setup uses specified TLS version."""
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker", "tls_version": "1.2"}
    )

    assert await mqtt.async_setup_entry(hass, entry)

    assert mock_MQTT.called

    assert mock_MQTT.mock_calls[0][2]["tls_version"] == ssl.PROTOCOL_TLSv1_2


async def test_setup_with_tls_config_of_v1_under_python36_only_uses_v1(hass, mock_MQTT):
    """Test setup uses TLSv1.0 if explicitly chosen."""
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker", "tls_version": "1.0"}
    )

    assert await mqtt.async_setup_entry(hass, entry)

    assert mock_MQTT.called
    assert mock_MQTT.mock_calls[0][2]["tls_version"] == ssl.PROTOCOL_TLSv1


async def test_birth_message(hass):
    """Test sending birth message."""
    mqtt_client = await async_mock_mqtt_client(
        hass,
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "birth",
                mqtt.ATTR_PAYLOAD: "birth",
            },
        },
    )
    calls = []
    mqtt_client.publish.side_effect = lambda *args: calls.append(args)
    hass.data["mqtt"]._mqtt_on_connect(None, None, 0, 0)
    await hass.async_block_till_done()
    assert calls[-1] == ("birth", "birth", 0, False)


async def test_mqtt_subscribes_topics_on_connect(hass):
    """Test subscription to topic on connect."""
    mqtt_client = await async_mock_mqtt_client(hass)

    hass.data["mqtt"].subscriptions = [
        mqtt.Subscription("topic/test", None),
        mqtt.Subscription("home/sensor", None, 2),
        mqtt.Subscription("still/pending", None),
        mqtt.Subscription("still/pending", None, 1),
    ]

    hass.add_job = mock.MagicMock()
    hass.data["mqtt"]._mqtt_on_connect(None, None, 0, 0)

    await hass.async_block_till_done()

    assert mqtt_client.disconnect.call_count == 0

    expected = {"topic/test": 0, "home/sensor": 2, "still/pending": 1}
    calls = {call[1][1]: call[1][2] for call in hass.add_job.mock_calls}
    assert calls == expected


async def test_setup_fails_without_config(hass):
    """Test if the MQTT component fails to load with no config."""
    assert not await async_setup_component(hass, mqtt.DOMAIN, {})


async def test_message_callback_exception_gets_logged(hass, caplog):
    """Test exception raised by message handler."""
    await async_mock_mqtt_component(hass)

    @callback
    def bad_handler(*args):
        """Record calls."""
        raise Exception("This is a bad message callback")

    await mqtt.async_subscribe(hass, "test-topic", bad_handler)
    async_fire_mqtt_message(hass, "test-topic", "test")
    await hass.async_block_till_done()

    assert (
        "Exception in bad_handler when handling msg on 'test-topic':"
        " 'test'" in caplog.text
    )


async def test_mqtt_ws_subscription(hass, hass_ws_client):
    """Test MQTT websocket subscription."""
    await async_mock_mqtt_component(hass)

    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/subscribe", "topic": "test-topic"})
    response = await client.receive_json()
    assert response["success"]

    async_fire_mqtt_message(hass, "test-topic", "test1")
    async_fire_mqtt_message(hass, "test-topic", "test2")

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "test1"

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "test2"

    # Unsubscribe
    await client.send_json({"id": 8, "type": "unsubscribe_events", "subscription": 5})
    response = await client.receive_json()
    assert response["success"]


async def test_dump_service(hass):
    """Test that we can dump a topic."""
    await async_mock_mqtt_component(hass)

    mock_open = mock.mock_open()

    await hass.services.async_call(
        "mqtt", "dump", {"topic": "bla/#", "duration": 3}, blocking=True
    )
    async_fire_mqtt_message(hass, "bla/1", "test1")
    async_fire_mqtt_message(hass, "bla/2", "test2")

    with mock.patch("homeassistant.components.mqtt.open", mock_open):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

    writes = mock_open.return_value.write.mock_calls
    assert len(writes) == 2
    assert writes[0][1][0] == "bla/1,test1\n"
    assert writes[1][1][0] == "bla/2,test2\n"


async def test_mqtt_ws_remove_discovered_device(
    hass, device_reg, entity_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device removal."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]

    # Verify device entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is None


async def test_mqtt_ws_remove_discovered_device_twice(
    hass, device_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device removal."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {"id": 6, "type": "mqtt/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == websocket_api.const.ERR_NOT_FOUND


async def test_mqtt_ws_remove_non_mqtt_device(
    hass, device_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device removal of device belonging to other domain."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == websocket_api.const.ERR_NOT_FOUND


async def test_mqtt_ws_get_device_debug_info(
    hass, device_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device debug info."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    config = {
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "state_topic": "foobar/sensor",
        "unique_id": "unique",
    }
    data = json.dumps(config)

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/device/debug_info", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]
    expected_result = {
        "entities": [
            {
                "entity_id": "sensor.mqtt_sensor",
                "topics": [{"topic": "foobar/sensor", "messages": []}],
                "discovery_data": {
                    "payload": config,
                    "topic": "homeassistant/sensor/bla/config",
                },
            }
        ],
        "triggers": [],
    }
    assert response["result"] == expected_result
