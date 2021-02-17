"""The tests for the MQTT component."""
import asyncio
from datetime import datetime, timedelta
import json
import ssl
from unittest.mock import AsyncMock, MagicMock, call, mock_open, patch

import pytest
import voluptuous as vol

from homeassistant.components import mqtt, websocket_api
from homeassistant.components.mqtt import debug_info
from homeassistant.components.mqtt.mixins import MQTT_ENTITY_DEVICE_INFO_SCHEMA
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_device_registry,
    mock_registry,
)
from tests.testing_config.custom_components.test.sensor import DEVICE_CLASSES


@pytest.fixture(autouse=True)
def mock_storage(hass_storage):
    """Autouse hass_storage for the TestCase tests."""


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def mock_mqtt():
    """Make sure connection is established."""
    with patch("homeassistant.components.mqtt.MQTT") as mock_mqtt:
        mock_mqtt.return_value.async_connect = AsyncMock(return_value=True)
        mock_mqtt.return_value.async_disconnect = AsyncMock(return_value=True)
        yield mock_mqtt


@pytest.fixture
def calls():
    """Fixture to record calls."""
    return []


@pytest.fixture
def record_calls(calls):
    """Fixture to record calls."""

    @callback
    def record_calls(*args):
        """Record calls."""
        calls.append(args)

    return record_calls


async def test_mqtt_connects_on_home_assistant_mqtt_setup(
    hass, mqtt_client_mock, mqtt_mock
):
    """Test if client is connected after mqtt init on bootstrap."""
    assert mqtt_client_mock.connect.call_count == 1


async def test_mqtt_disconnects_on_home_assistant_stop(hass, mqtt_mock):
    """Test if client stops on HA stop."""
    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mqtt_mock.async_disconnect.called


async def test_publish_calls_service(hass, mqtt_mock, calls, record_calls):
    """Test the publishing of call to services."""
    hass.bus.async_listen_once(EVENT_CALL_SERVICE, record_calls)

    mqtt.async_publish(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0][0].data["service_data"][mqtt.ATTR_TOPIC] == "test-topic"
    assert calls[0][0].data["service_data"][mqtt.ATTR_PAYLOAD] == "test-payload"


async def test_service_call_without_topic_does_not_publish(hass, mqtt_mock):
    """Test the service call if topic is missing."""
    hass.bus.fire(
        EVENT_CALL_SERVICE,
        {ATTR_DOMAIN: mqtt.DOMAIN, ATTR_SERVICE: mqtt.SERVICE_PUBLISH},
    )
    await hass.async_block_till_done()
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_template_payload_renders_template(hass, mqtt_mock):
    """Test the service call with rendered template.

    If 'payload_template' is provided and 'payload' is not, then render it.
    """
    mqtt.async_publish_template(hass, "test/topic", "{{ 1+1 }}")
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] == "2"


async def test_service_call_with_payload_doesnt_render_template(hass, mqtt_mock):
    """Test the service call with unrendered template.

    If both 'payload' and 'payload_template' are provided then fail.
    """
    payload = "not a template"
    payload_template = "a template"
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: "test/topic",
                mqtt.ATTR_PAYLOAD: payload,
                mqtt.ATTR_PAYLOAD_TEMPLATE: payload_template,
            },
            blocking=True,
        )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_ascii_qos_retain_flags(hass, mqtt_mock):
    """Test the service call with args that can be misinterpreted.

    Empty payload message and ascii formatted qos and retain flags.
    """
    await hass.services.async_call(
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
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][2] == 2
    assert not mqtt_mock.async_publish.call_args[0][3]


def test_validate_topic():
    """Test topic name/filter validation."""
    # Invalid UTF-8, must not contain U+D800 to U+DFFF.
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\ud800")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\udfff")
    # Topic MUST NOT be empty
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("")
    # Topic MUST NOT be longer than 65535 encoded bytes.
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("ü" * 32768)
    # UTF-8 MUST NOT include null character
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("bad\0one")

    # Topics "SHOULD NOT" include these special characters
    # (not MUST NOT, RFC2119). The receiver MAY close the connection.
    mqtt.util.valid_topic("\u0001")
    mqtt.util.valid_topic("\u001F")
    mqtt.util.valid_topic("\u009F")
    mqtt.util.valid_topic("\u009F")
    mqtt.util.valid_topic("\uffff")


def test_validate_subscribe_topic():
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


def test_validate_publish_topic():
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


def test_entity_device_info_schema():
    """Test MQTT entity device info validation."""
    # just identifier
    MQTT_ENTITY_DEVICE_INFO_SCHEMA({"identifiers": ["abcd"]})
    MQTT_ENTITY_DEVICE_INFO_SCHEMA({"identifiers": "abcd"})
    # just connection
    MQTT_ENTITY_DEVICE_INFO_SCHEMA({"connections": [["mac", "02:5b:26:a8:dc:12"]]})
    # full device info
    MQTT_ENTITY_DEVICE_INFO_SCHEMA(
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
    MQTT_ENTITY_DEVICE_INFO_SCHEMA(
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
        MQTT_ENTITY_DEVICE_INFO_SCHEMA(
            {
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
            }
        )
    # empty identifiers
    with pytest.raises(vol.Invalid):
        MQTT_ENTITY_DEVICE_INFO_SCHEMA(
            {"identifiers": [], "connections": [], "name": "Beer"}
        )


async def test_receiving_non_utf8_message_gets_logged(
    hass, mqtt_mock, calls, record_calls, caplog
):
    """Test receiving a non utf8 encoded message."""
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", b"\x9a")

    await hass.async_block_till_done()
    assert (
        "Can't decode payload b'\\x9a' on test-topic with encoding utf-8" in caplog.text
    )


async def test_all_subscriptions_run_when_decode_fails(
    hass, mqtt_mock, calls, record_calls
):
    """Test all other subscriptions still run when decode fails for one."""
    await mqtt.async_subscribe(hass, "test-topic", record_calls, encoding="ascii")
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", TEMP_CELSIUS)

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_topic(hass, mqtt_mock, calls, record_calls):
    """Test the subscription of a topic."""
    unsub = await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic"
    assert calls[0][0].payload == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_deprecated(hass, mqtt_mock):
    """Test the subscription of a topic using deprecated callback signature."""
    calls = []

    @callback
    def record_calls(topic, payload, qos):
        """Record calls."""
        calls.append((topic, payload, qos))

    unsub = await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0] == "test-topic"
    assert calls[0][1] == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_deprecated_async(hass, mqtt_mock):
    """Test the subscription of a topic using deprecated callback signature."""
    calls = []

    async def record_calls(topic, payload, qos):
        """Record calls."""
        calls.append((topic, payload, qos))

    unsub = await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0] == "test-topic"
    assert calls[0][1] == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_topic_not_match(hass, mqtt_mock, calls, record_calls):
    """Test if subscribed topic is not a match."""
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard(hass, mqtt_mock, calls, record_calls):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "test-topic/+/on", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic/bier/on"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_no_subtree_match(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "test-topic/+/on", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_root_topic_no_subtree_match(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic-123", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_subtree_wildcard_subtree_topic(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic/bier/on"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_subtree_wildcard_root_topic(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_subtree_wildcard_no_match(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_and_wildcard_root_topic(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "hi/test-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_and_wildcard_subtree_topic(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/test-topic/here-iam", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "hi/test-topic/here-iam"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_and_wildcard_level_no_match(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/here-iam/test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_and_wildcard_no_match(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_sys_root(hass, mqtt_mock, calls, record_calls):
    """Test the subscription of $ root topics."""
    await mqtt.async_subscribe(hass, "$test-topic/subtree/on", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/subtree/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "$test-topic/subtree/on"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_sys_root_and_wildcard_topic(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of $ root and wildcard topics."""
    await mqtt.async_subscribe(hass, "$test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/some-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "$test-topic/some-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_sys_root_and_wildcard_subtree_topic(
    hass, mqtt_mock, calls, record_calls
):
    """Test the subscription of $ root and wildcard subtree topics."""
    await mqtt.async_subscribe(hass, "$test-topic/subtree/#", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/subtree/some-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "$test-topic/subtree/some-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_special_characters(hass, mqtt_mock, calls, record_calls):
    """Test the subscription to topics with special characters."""
    topic = "/test-topic/$(.)[^]{-}"
    payload = "p4y.l[]a|> ?"

    await mqtt.async_subscribe(hass, topic, record_calls)

    async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == topic
    assert calls[0][0].payload == payload


async def test_subscribe_same_topic(hass, mqtt_client_mock, mqtt_mock):
    """
    Test subscring to same topic twice and simulate retained messages.

    When subscribing to the same topic again, SUBSCRIBE must be sent to the broker again
    for it to resend any retained messages.
    """

    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a = MagicMock()
    await mqtt.async_subscribe(hass, "test/state", calls_a)
    async_fire_mqtt_message(
        hass, "test/state", "online"
    )  # Simulate a (retained) message
    await hass.async_block_till_done()
    assert calls_a.called
    mqtt_client_mock.subscribe.assert_called()
    calls_a.reset_mock()
    mqtt_client_mock.reset_mock()

    calls_b = MagicMock()
    await mqtt.async_subscribe(hass, "test/state", calls_b)
    async_fire_mqtt_message(
        hass, "test/state", "online"
    )  # Simulate a (retained) message
    await hass.async_block_till_done()
    assert calls_a.called
    assert calls_b.called
    mqtt_client_mock.subscribe.assert_called()


async def test_not_calling_unsubscribe_with_active_subscribers(
    hass, mqtt_client_mock, mqtt_mock
):
    """Test not calling unsubscribe() when other subscribers are active."""
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test/state", None)
    await mqtt.async_subscribe(hass, "test/state", None)
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.called

    unsub()
    await hass.async_block_till_done()
    assert not mqtt_client_mock.unsubscribe.called


@pytest.mark.parametrize(
    "mqtt_config",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
async def test_restore_subscriptions_on_reconnect(hass, mqtt_client_mock, mqtt_mock):
    """Test subscriptions are restored on reconnect."""
    # Fake that the client is connected
    mqtt_mock().connected = True

    await mqtt.async_subscribe(hass, "test/state", None)
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.call_count == 1

    mqtt_mock._mqtt_on_disconnect(None, None, 0)
    with patch("homeassistant.components.mqtt.DISCOVERY_COOLDOWN", 0):
        mqtt_mock._mqtt_on_connect(None, None, None, 0)
        await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.call_count == 2


@pytest.mark.parametrize(
    "mqtt_config",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
async def test_restore_all_active_subscriptions_on_reconnect(
    hass, mqtt_client_mock, mqtt_mock
):
    """Test active subscriptions are restored correctly on reconnect."""
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test/state", None, qos=2)
    await mqtt.async_subscribe(hass, "test/state", None)
    await mqtt.async_subscribe(hass, "test/state", None, qos=1)
    await hass.async_block_till_done()

    expected = [
        call("test/state", 2),
        call("test/state", 0),
        call("test/state", 1),
    ]
    assert mqtt_client_mock.subscribe.mock_calls == expected

    unsub()
    await hass.async_block_till_done()
    assert mqtt_client_mock.unsubscribe.call_count == 0

    mqtt_mock._mqtt_on_disconnect(None, None, 0)
    with patch("homeassistant.components.mqtt.DISCOVERY_COOLDOWN", 0):
        mqtt_mock._mqtt_on_connect(None, None, None, 0)
        await hass.async_block_till_done()

    expected.append(call("test/state", 1))
    assert mqtt_client_mock.subscribe.mock_calls == expected


async def test_setup_logs_error_if_no_connect_broker(hass, caplog):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = lambda *args: 1
        assert await mqtt.async_setup_entry(hass, entry)
        assert "Failed to connect to MQTT server:" in caplog.text


async def test_setup_raises_ConfigEntryNotReady_if_no_connect_broker(hass, caplog):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = MagicMock(side_effect=OSError("Connection error"))
        assert await mqtt.async_setup_entry(hass, entry)
        assert "Failed to connect to MQTT server due to exception:" in caplog.text


async def test_setup_uses_certificate_on_certificate_set_to_auto(hass):
    """Test setup uses bundled certs when certificate is set to auto."""
    calls = []

    def mock_tls_set(certificate, certfile=None, keyfile=None, tls_version=None):
        calls.append((certificate, certfile, keyfile, tls_version))

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().tls_set = mock_tls_set
        entry = MockConfigEntry(
            domain=mqtt.DOMAIN,
            data={mqtt.CONF_BROKER: "test-broker", "certificate": "auto"},
        )

        assert await mqtt.async_setup_entry(hass, entry)

        assert calls

        import certifi

        expectedCertificate = certifi.where()
        # assert mock_mqtt.mock_calls[0][1][2]["certificate"] == expectedCertificate
        assert calls[0][0] == expectedCertificate


async def test_setup_without_tls_config_uses_tlsv1_under_python36(hass):
    """Test setup defaults to TLSv1 under python3.6."""
    calls = []

    def mock_tls_set(certificate, certfile=None, keyfile=None, tls_version=None):
        calls.append((certificate, certfile, keyfile, tls_version))

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().tls_set = mock_tls_set
        entry = MockConfigEntry(
            domain=mqtt.DOMAIN,
            data={"certificate": "auto", mqtt.CONF_BROKER: "test-broker"},
        )

        assert await mqtt.async_setup_entry(hass, entry)

        assert calls

        import sys

        if sys.hexversion >= 0x03060000:
            expectedTlsVersion = ssl.PROTOCOL_TLS  # pylint: disable=no-member
        else:
            expectedTlsVersion = ssl.PROTOCOL_TLSv1

        assert calls[0][3] == expectedTlsVersion


@pytest.mark.parametrize(
    "mqtt_config",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "birth",
                mqtt.ATTR_PAYLOAD: "birth",
            },
        }
    ],
)
async def test_custom_birth_message(hass, mqtt_client_mock, mqtt_mock):
    """Test sending birth message."""
    birth = asyncio.Event()

    async def wait_birth(topic, payload, qos):
        """Handle birth message."""
        birth.set()

    with patch("homeassistant.components.mqtt.DISCOVERY_COOLDOWN", 0.1):
        await mqtt.async_subscribe(hass, "birth", wait_birth)
        mqtt_mock._mqtt_on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await birth.wait()
        mqtt_client_mock.publish.assert_called_with("birth", "birth", 0, False)


@pytest.mark.parametrize(
    "mqtt_config",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "homeassistant/status",
                mqtt.ATTR_PAYLOAD: "online",
            },
        }
    ],
)
async def test_default_birth_message(hass, mqtt_client_mock, mqtt_mock):
    """Test sending birth message."""
    birth = asyncio.Event()

    async def wait_birth(topic, payload, qos):
        """Handle birth message."""
        birth.set()

    with patch("homeassistant.components.mqtt.DISCOVERY_COOLDOWN", 0.1):
        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        mqtt_mock._mqtt_on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await birth.wait()
        mqtt_client_mock.publish.assert_called_with(
            "homeassistant/status", "online", 0, False
        )


@pytest.mark.parametrize(
    "mqtt_config",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_BIRTH_MESSAGE: {}}],
)
async def test_no_birth_message(hass, mqtt_client_mock, mqtt_mock):
    """Test disabling birth message."""
    with patch("homeassistant.components.mqtt.DISCOVERY_COOLDOWN", 0.1):
        mqtt_mock._mqtt_on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await asyncio.sleep(0.2)
        mqtt_client_mock.publish.assert_not_called()


@pytest.mark.parametrize(
    "mqtt_config",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_WILL_MESSAGE: {
                mqtt.ATTR_TOPIC: "death",
                mqtt.ATTR_PAYLOAD: "death",
            },
        }
    ],
)
async def test_custom_will_message(hass, mqtt_client_mock, mqtt_mock):
    """Test will message."""
    mqtt_client_mock.will_set.assert_called_with(
        topic="death", payload="death", qos=0, retain=False
    )


async def test_default_will_message(hass, mqtt_client_mock, mqtt_mock):
    """Test will message."""
    mqtt_client_mock.will_set.assert_called_with(
        topic="homeassistant/status", payload="offline", qos=0, retain=False
    )


@pytest.mark.parametrize(
    "mqtt_config",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_WILL_MESSAGE: {}}],
)
async def test_no_will_message(hass, mqtt_client_mock, mqtt_mock):
    """Test will message."""
    mqtt_client_mock.will_set.assert_not_called()


@pytest.mark.parametrize(
    "mqtt_config",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {},
            mqtt.CONF_DISCOVERY: False,
        }
    ],
)
async def test_mqtt_subscribes_topics_on_connect(hass, mqtt_client_mock, mqtt_mock):
    """Test subscription to topic on connect."""
    await mqtt.async_subscribe(hass, "topic/test", None)
    await mqtt.async_subscribe(hass, "home/sensor", None, 2)
    await mqtt.async_subscribe(hass, "still/pending", None)
    await mqtt.async_subscribe(hass, "still/pending", None, 1)

    hass.add_job = MagicMock()
    mqtt_mock._mqtt_on_connect(None, None, 0, 0)

    await hass.async_block_till_done()

    assert mqtt_client_mock.disconnect.call_count == 0

    expected = {"topic/test": 0, "home/sensor": 2, "still/pending": 1}
    calls = {call[1][1]: call[1][2] for call in hass.add_job.mock_calls}
    assert calls == expected


async def test_setup_fails_without_config(hass):
    """Test if the MQTT component fails to load with no config."""
    assert not await async_setup_component(hass, mqtt.DOMAIN, {})


@pytest.mark.no_fail_on_log_exception
async def test_message_callback_exception_gets_logged(hass, caplog, mqtt_mock):
    """Test exception raised by message handler."""

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


async def test_mqtt_ws_subscription(hass, hass_ws_client, mqtt_mock):
    """Test MQTT websocket subscription."""
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


async def test_dump_service(hass, mqtt_mock):
    """Test that we can dump a topic."""
    mopen = mock_open()

    await hass.services.async_call(
        "mqtt", "dump", {"topic": "bla/#", "duration": 3}, blocking=True
    )
    async_fire_mqtt_message(hass, "bla/1", "test1")
    async_fire_mqtt_message(hass, "bla/2", "test2")

    with patch("homeassistant.components.mqtt.open", mopen):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

    writes = mopen.return_value.write.mock_calls
    assert len(writes) == 2
    assert writes[0][1][0] == "bla/1,test1\n"
    assert writes[1][1][0] == "bla/2,test2\n"


async def test_mqtt_ws_remove_discovered_device(
    hass, device_reg, entity_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device removal."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]

    # Verify device entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is None


async def test_mqtt_ws_remove_discovered_device_twice(
    hass, device_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device removal."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
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


async def test_mqtt_ws_remove_discovered_device_same_topic(
    hass, device_reg, hass_ws_client, mqtt_mock
):
    """Test MQTT websocket device removal."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "availability_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
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
                "subscriptions": [{"topic": "foobar/sensor", "messages": []}],
                "discovery_data": {
                    "payload": config,
                    "topic": "homeassistant/sensor/bla/config",
                },
            }
        ],
        "triggers": [],
    }
    assert response["result"] == expected_result


async def test_debug_info_multiple_devices(hass, mqtt_mock):
    """Test we get correct debug_info when multiple devices are present."""
    devices = [
        {
            "domain": "sensor",
            "config": {
                "device": {"identifiers": ["0AFFD0"]},
                "platform": "mqtt",
                "state_topic": "test-topic-sensor",
                "unique_id": "unique",
            },
        },
        {
            "domain": "binary_sensor",
            "config": {
                "device": {"identifiers": ["0AFFD1"]},
                "platform": "mqtt",
                "state_topic": "test-topic-binary-sensor",
                "unique_id": "unique",
            },
        },
        {
            "domain": "device_automation",
            "config": {
                "automation_type": "trigger",
                "device": {"identifiers": ["0AFFD2"]},
                "platform": "mqtt",
                "topic": "test-topic1",
                "type": "foo",
                "subtype": "bar",
            },
        },
        {
            "domain": "device_automation",
            "config": {
                "automation_type": "trigger",
                "device": {"identifiers": ["0AFFD3"]},
                "platform": "mqtt",
                "topic": "test-topic2",
                "type": "ikk",
                "subtype": "baz",
            },
        },
    ]

    registry = await hass.helpers.device_registry.async_get_registry()

    for d in devices:
        data = json.dumps(d["config"])
        domain = d["domain"]
        id = d["config"]["device"]["identifiers"][0]
        async_fire_mqtt_message(hass, f"homeassistant/{domain}/{id}/config", data)
        await hass.async_block_till_done()

    for d in devices:
        domain = d["domain"]
        id = d["config"]["device"]["identifiers"][0]
        device = registry.async_get_device({("mqtt", id)})
        assert device is not None

        debug_info_data = await debug_info.info_for_device(hass, device.id)
        if d["domain"] != "device_automation":
            assert len(debug_info_data["entities"]) == 1
            assert len(debug_info_data["triggers"]) == 0
            discovery_data = debug_info_data["entities"][0]["discovery_data"]
            assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
            topic = d["config"]["state_topic"]
            assert {"topic": topic, "messages": []} in debug_info_data["entities"][0][
                "subscriptions"
            ]
        else:
            assert len(debug_info_data["entities"]) == 0
            assert len(debug_info_data["triggers"]) == 1
            discovery_data = debug_info_data["triggers"][0]["discovery_data"]

        assert discovery_data["topic"] == f"homeassistant/{domain}/{id}/config"
        assert discovery_data["payload"] == d["config"]


async def test_debug_info_multiple_entities_triggers(hass, mqtt_mock):
    """Test we get correct debug_info for a device with multiple entities and triggers."""
    config = [
        {
            "domain": "sensor",
            "config": {
                "device": {"identifiers": ["0AFFD0"]},
                "platform": "mqtt",
                "state_topic": "test-topic-sensor",
                "unique_id": "unique",
            },
        },
        {
            "domain": "binary_sensor",
            "config": {
                "device": {"identifiers": ["0AFFD0"]},
                "platform": "mqtt",
                "state_topic": "test-topic-binary-sensor",
                "unique_id": "unique",
            },
        },
        {
            "domain": "device_automation",
            "config": {
                "automation_type": "trigger",
                "device": {"identifiers": ["0AFFD0"]},
                "platform": "mqtt",
                "topic": "test-topic1",
                "type": "foo",
                "subtype": "bar",
            },
        },
        {
            "domain": "device_automation",
            "config": {
                "automation_type": "trigger",
                "device": {"identifiers": ["0AFFD0"]},
                "platform": "mqtt",
                "topic": "test-topic2",
                "type": "ikk",
                "subtype": "baz",
            },
        },
    ]

    registry = await hass.helpers.device_registry.async_get_registry()

    for c in config:
        data = json.dumps(c["config"])
        domain = c["domain"]
        # Use topic as discovery_id
        id = c["config"].get("topic", c["config"].get("state_topic"))
        async_fire_mqtt_message(hass, f"homeassistant/{domain}/{id}/config", data)
        await hass.async_block_till_done()

    device_id = config[0]["config"]["device"]["identifiers"][0]
    device = registry.async_get_device({("mqtt", device_id)})
    assert device is not None
    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 2
    assert len(debug_info_data["triggers"]) == 2

    for c in config:
        # Test we get debug info for each entity and trigger
        domain = c["domain"]
        # Use topic as discovery_id
        id = c["config"].get("topic", c["config"].get("state_topic"))

        if c["domain"] != "device_automation":
            discovery_data = [e["discovery_data"] for e in debug_info_data["entities"]]
            topic = c["config"]["state_topic"]
            assert {"topic": topic, "messages": []} in [
                t for e in debug_info_data["entities"] for t in e["subscriptions"]
            ]
        else:
            discovery_data = [e["discovery_data"] for e in debug_info_data["triggers"]]

        assert {
            "topic": f"homeassistant/{domain}/{id}/config",
            "payload": c["config"],
        } in discovery_data


async def test_debug_info_non_mqtt(hass, device_reg, entity_reg):
    """Test we get empty debug_info for a device with non MQTT entities."""
    DOMAIN = "sensor"
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in DEVICE_CLASSES:
        entity_reg.async_get_or_create(
            DOMAIN,
            "test",
            platform.ENTITIES[device_class].unique_id,
            device_id=device_entry.id,
        )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "test"}})

    debug_info_data = await debug_info.info_for_device(hass, device_entry.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 0


async def test_debug_info_wildcard(hass, mqtt_mock):
    """Test debug info."""
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        async_fire_mqtt_message(hass, "sensor/abc", "123")

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {
        "topic": "sensor/#",
        "messages": [
            {
                "payload": "123",
                "qos": 0,
                "retain": False,
                "time": start_dt,
                "topic": "sensor/abc",
            }
        ],
    } in debug_info_data["entities"][0]["subscriptions"]


async def test_debug_info_filter_same(hass, mqtt_mock):
    """Test debug info removes messages with same timestamp."""
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    dt1 = datetime(2019, 1, 1, 0, 0, 0)
    dt2 = datetime(2019, 1, 1, 0, 0, 1)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = dt1
        async_fire_mqtt_message(hass, "sensor/abc", "123")
        async_fire_mqtt_message(hass, "sensor/abc", "123")
        dt_utcnow.return_value = dt2
        async_fire_mqtt_message(hass, "sensor/abc", "123")

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert len(debug_info_data["entities"][0]["subscriptions"][0]["messages"]) == 2
    assert {
        "topic": "sensor/#",
        "messages": [
            {
                "payload": "123",
                "qos": 0,
                "retain": False,
                "time": dt1,
                "topic": "sensor/abc",
            },
            {
                "payload": "123",
                "qos": 0,
                "retain": False,
                "time": dt2,
                "topic": "sensor/abc",
            },
        ],
    } == debug_info_data["entities"][0]["subscriptions"][0]


async def test_debug_info_same_topic(hass, mqtt_mock):
    """Test debug info."""
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/status",
        "availability_topic": "sensor/status",
        "unique_id": "veryunique",
    }

    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/status", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        async_fire_mqtt_message(hass, "sensor/status", "123", qos=0, retain=False)

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {
        "payload": "123",
        "qos": 0,
        "retain": False,
        "time": start_dt,
        "topic": "sensor/status",
    } in debug_info_data["entities"][0]["subscriptions"][0]["messages"]

    config["availability_topic"] = "sensor/availability"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        async_fire_mqtt_message(hass, "sensor/status", "123", qos=0, retain=False)


async def test_debug_info_qos_retain(hass, mqtt_mock):
    """Test debug info."""
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        async_fire_mqtt_message(hass, "sensor/abc", "123", qos=0, retain=False)
        async_fire_mqtt_message(hass, "sensor/abc", "123", qos=1, retain=True)
        async_fire_mqtt_message(hass, "sensor/abc", "123", qos=2, retain=False)

    debug_info_data = await debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {
        "payload": "123",
        "qos": 0,
        "retain": False,
        "time": start_dt,
        "topic": "sensor/abc",
    } in debug_info_data["entities"][0]["subscriptions"][0]["messages"]
    assert {
        "payload": "123",
        "qos": 1,
        "retain": True,
        "time": start_dt,
        "topic": "sensor/abc",
    } in debug_info_data["entities"][0]["subscriptions"][0]["messages"]
    assert {
        "payload": "123",
        "qos": 2,
        "retain": False,
        "time": start_dt,
        "topic": "sensor/abc",
    } in debug_info_data["entities"][0]["subscriptions"][0]["messages"]


async def test_publish_json_from_template(hass, mqtt_mock):
    """Test the publishing of call to services."""
    test_str = "{'valid': 'python', 'invalid': 'json'}"
    test_str_tpl = "{'valid': '{{ \"python\" }}', 'invalid': 'json'}"

    await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script_payload": {
                    "sequence": {
                        "service": "mqtt.publish",
                        "data": {"topic": "test-topic", "payload": test_str_tpl},
                    }
                },
                "test_script_payload_template": {
                    "sequence": {
                        "service": "mqtt.publish",
                        "data": {
                            "topic": "test-topic",
                            "payload_template": test_str_tpl,
                        },
                    }
                },
            }
        },
    )

    await hass.services.async_call("script", "test_script_payload", blocking=True)
    await hass.async_block_till_done()

    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] == test_str

    mqtt_mock.async_publish.reset_mock()
    assert not mqtt_mock.async_publish.called

    await hass.services.async_call(
        "script", "test_script_payload_template", blocking=True
    )
    await hass.async_block_till_done()

    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] == test_str
