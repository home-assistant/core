"""The tests for the MQTT component."""
import asyncio
import copy
from datetime import datetime, timedelta
from functools import partial
import json
import ssl
from unittest.mock import ANY, AsyncMock, MagicMock, call, mock_open, patch

import pytest
import voluptuous as vol
import yaml

from homeassistant import config as hass_config
from homeassistant.components import mqtt
from homeassistant.components.mqtt import CONFIG_SCHEMA, debug_info
from homeassistant.components.mqtt.mixins import MQTT_ENTITY_DEVICE_INFO_SCHEMA
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELSIUS,
    Platform,
)
import homeassistant.core as ha
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, template
from homeassistant.helpers.entity import Entity
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .test_common import (
    help_test_entry_reload_with_new_config,
    help_test_setup_manual_entity_from_yaml,
)

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_device_registry,
    mock_registry,
    mock_restore_cache,
)
from tests.testing_config.custom_components.test.sensor import DEVICE_CLASSES


class RecordCallsPartial(partial):
    """Wrapper class for partial."""

    __name__ = "RecordCallPartialTest"


@pytest.fixture(autouse=True)
def sensor_platforms_only():
    """Only setup the sensor platforms to speed up tests."""
    with patch(
        "homeassistant.components.mqtt.PLATFORMS",
        [Platform.SENSOR, Platform.BINARY_SENSOR],
    ):
        yield


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


@pytest.fixture
def empty_mqtt_config(hass, tmp_path):
    """Fixture to provide an empty config from yaml."""
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config_file.write_text("")

    with patch.object(
        hass_config, "YAML_CONFIG_FILE", new_yaml_config_file
    ) as empty_config:
        yield empty_config


async def test_mqtt_connects_on_home_assistant_mqtt_setup(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test if client is connected after mqtt init on bootstrap."""
    await mqtt_mock_entry_no_yaml_config()
    assert mqtt_client_mock.connect.call_count == 1


async def test_mqtt_disconnects_on_home_assistant_stop(
    hass, mqtt_mock_entry_no_yaml_config, mqtt_client_mock
):
    """Test if client stops on HA stop."""
    await mqtt_mock_entry_no_yaml_config()
    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mqtt_client_mock.loop_stop.call_count == 1


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_mqtt_await_ack_at_disconnect(
    hass,
):
    """Test if ACK is awaited correctly when disconnecting."""

    class FakeInfo:
        """Returns a simulated client publish response."""

        mid = 100
        rc = 0

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = MagicMock(return_value=0)
        mock_client().publish = MagicMock(return_value=FakeInfo())
        entry = MockConfigEntry(
            domain=mqtt.DOMAIN,
            data={"certificate": "auto", mqtt.CONF_BROKER: "test-broker"},
        )
        entry.add_to_hass(hass)
        assert await mqtt.async_setup_entry(hass, entry)
        mqtt_client = mock_client.return_value

        # publish from MQTT client without awaiting
        hass.async_create_task(
            mqtt.async_publish(hass, "test-topic", "some-payload", 0, False)
        )
        await asyncio.sleep(0)
        # Simulate late ACK callback from client with mid 100
        mqtt_client.on_publish(0, 0, 100)
        # disconnect the MQTT client
        await hass.async_stop()
        await hass.async_block_till_done()
        # assert the payload was sent through the client
        assert mqtt_client.publish.called
        assert mqtt_client.publish.call_args[0] == (
            "test-topic",
            "some-payload",
            0,
            False,
        )


async def test_publish(hass, mqtt_mock_entry_no_yaml_config):
    """Test the publish function."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_publish(hass, "test-topic", "test-payload")
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0] == (
        "test-topic",
        "test-payload",
        0,
        False,
    )
    mqtt_mock.reset_mock()

    await mqtt.async_publish(hass, "test-topic", "test-payload", 2, True)
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0] == (
        "test-topic",
        "test-payload",
        2,
        True,
    )
    mqtt_mock.reset_mock()

    mqtt.publish(hass, "test-topic2", "test-payload2")
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0] == (
        "test-topic2",
        "test-payload2",
        0,
        False,
    )
    mqtt_mock.reset_mock()

    mqtt.publish(hass, "test-topic2", "test-payload2", 2, True)
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0] == (
        "test-topic2",
        "test-payload2",
        2,
        True,
    )
    mqtt_mock.reset_mock()

    # test binary pass-through
    mqtt.publish(
        hass,
        "test-topic3",
        b"\xde\xad\xbe\xef",
        0,
        False,
    )
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0] == (
        "test-topic3",
        b"\xde\xad\xbe\xef",
        0,
        False,
    )
    mqtt_mock.reset_mock()


async def test_convert_outgoing_payload(hass):
    """Test the converting of outgoing MQTT payloads without template."""
    command_template = mqtt.MqttCommandTemplate(None, hass=hass)
    assert command_template.async_render(b"\xde\xad\xbe\xef") == b"\xde\xad\xbe\xef"

    assert (
        command_template.async_render("b'\\xde\\xad\\xbe\\xef'")
        == "b'\\xde\\xad\\xbe\\xef'"
    )

    assert command_template.async_render(1234) == 1234

    assert command_template.async_render(1234.56) == 1234.56

    assert command_template.async_render(None) is None


async def test_command_template_value(hass):
    """Test the rendering of MQTT command template."""

    variables = {"id": 1234, "some_var": "beer"}

    # test rendering value
    tpl = template.Template("{{ value + 1 }}", hass=hass)
    cmd_tpl = mqtt.MqttCommandTemplate(tpl, hass=hass)
    assert cmd_tpl.async_render(4321) == "4322"

    # test variables at rendering
    tpl = template.Template("{{ some_var }}", hass=hass)
    cmd_tpl = mqtt.MqttCommandTemplate(tpl, hass=hass)
    assert cmd_tpl.async_render(None, variables=variables) == "beer"


async def test_command_template_variables(hass, mqtt_mock_entry_with_yaml_config):
    """Test the rendering of entity variables."""
    topic = "test/select"

    fake_state = ha.State("select.test_select", "milk")
    mock_restore_cache(hass, (fake_state,))

    assert await async_setup_component(
        hass,
        "select",
        {
            "select": {
                "platform": "mqtt",
                "command_topic": topic,
                "name": "Test Select",
                "options": ["milk", "beer"],
                "command_template": '{"option": "{{ value }}", "entity_id": "{{ entity_id }}", "name": "{{ name }}", "this_object_state": "{{ this.state }}"}',
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("select.test_select")
    assert state.state == "milk"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test_select", "option": "beer"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        topic,
        '{"option": "beer", "entity_id": "select.test_select", "name": "Test Select", "this_object_state": "milk"}',
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("select.test_select")
    assert state.state == "beer"

    # Test that TemplateStateFromEntityId is not called again
    with patch(
        "homeassistant.helpers.template.TemplateStateFromEntityId", MagicMock()
    ) as template_state_calls:
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.test_select", "option": "milk"},
            blocking=True,
        )
        assert template_state_calls.call_count == 0
        state = hass.states.get("select.test_select")
        assert state.state == "milk"


async def test_value_template_value(hass):
    """Test the rendering of MQTT value template."""

    variables = {"id": 1234, "some_var": "beer"}

    # test rendering value
    tpl = template.Template("{{ value_json.id }}")
    val_tpl = mqtt.MqttValueTemplate(tpl, hass=hass)
    assert val_tpl.async_render_with_possible_json_value('{"id": 4321}') == "4321"

    # test variables at rendering
    tpl = template.Template("{{ value_json.id }} {{ some_var }} {{ code }}")
    val_tpl = mqtt.MqttValueTemplate(tpl, hass=hass, config_attributes={"code": 1234})
    assert (
        val_tpl.async_render_with_possible_json_value(
            '{"id": 4321}', variables=variables
        )
        == "4321 beer 1234"
    )

    # test with default value if an error occurs due to an invalid template
    tpl = template.Template("{{ value_json.id | as_datetime }}")
    val_tpl = mqtt.MqttValueTemplate(tpl, hass=hass)
    assert (
        val_tpl.async_render_with_possible_json_value('{"otherid": 4321}', "my default")
        == "my default"
    )

    # test value template with entity
    entity = Entity()
    entity.hass = hass
    entity.entity_id = "select.test"
    tpl = template.Template("{{ value_json.id }}")
    val_tpl = mqtt.MqttValueTemplate(tpl, entity=entity)
    assert val_tpl.async_render_with_possible_json_value('{"id": 4321}') == "4321"

    # test this object in a template
    tpl2 = template.Template("{{ this.entity_id }}")
    val_tpl2 = mqtt.MqttValueTemplate(tpl2, entity=entity)
    assert val_tpl2.async_render_with_possible_json_value("bla") == "select.test"

    with patch(
        "homeassistant.helpers.template.TemplateStateFromEntityId", MagicMock()
    ) as template_state_calls:
        tpl3 = template.Template("{{ this.entity_id }}")
        val_tpl3 = mqtt.MqttValueTemplate(tpl3, entity=entity)
        val_tpl3.async_render_with_possible_json_value("call1")
        val_tpl3.async_render_with_possible_json_value("call2")
        assert template_state_calls.call_count == 1


async def test_service_call_without_topic_does_not_publish(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call if topic is missing."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {},
            blocking=True,
        )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_topic_and_topic_template_does_not_publish(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with topic/topic template.

    If both 'topic' and 'topic_template' are provided then fail.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    topic = "test/topic"
    topic_template = "test/{{ 'topic' }}"
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: topic,
                mqtt.ATTR_TOPIC_TEMPLATE: topic_template,
                mqtt.ATTR_PAYLOAD: "payload",
            },
            blocking=True,
        )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_invalid_topic_template_does_not_publish(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with a problematic topic template."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {
            mqtt.ATTR_TOPIC_TEMPLATE: "test/{{ 1 | no_such_filter }}",
            mqtt.ATTR_PAYLOAD: "payload",
        },
        blocking=True,
    )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_template_topic_renders_template(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with rendered topic template.

    If 'topic_template' is provided and 'topic' is not, then render it.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {
            mqtt.ATTR_TOPIC_TEMPLATE: "test/{{ 1+1 }}",
            mqtt.ATTR_PAYLOAD: "payload",
        },
        blocking=True,
    )
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][0] == "test/2"


async def test_service_call_with_template_topic_renders_invalid_topic(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with rendered, invalid topic template.

    If a wildcard topic is rendered, then fail.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {
            mqtt.ATTR_TOPIC_TEMPLATE: "test/{{ '+' if True else 'topic' }}/topic",
            mqtt.ATTR_PAYLOAD: "payload",
        },
        blocking=True,
    )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_invalid_rendered_template_topic_doesnt_render_template(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with unrendered template.

    If both 'payload' and 'payload_template' are provided then fail.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
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


async def test_service_call_with_template_payload_renders_template(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with rendered template.

    If 'payload_template' is provided and 'payload' is not, then render it.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {mqtt.ATTR_TOPIC: "test/topic", mqtt.ATTR_PAYLOAD_TEMPLATE: "{{ 4+4 }}"},
        blocking=True,
    )
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] == "8"
    mqtt_mock.reset_mock()

    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {
            mqtt.ATTR_TOPIC: "test/topic",
            mqtt.ATTR_PAYLOAD_TEMPLATE: "{{ (4+4) | pack('B') }}",
        },
        blocking=True,
    )
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] == b"\x08"
    mqtt_mock.reset_mock()


async def test_service_call_with_bad_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test the service call with a bad template does not publish."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {mqtt.ATTR_TOPIC: "test/topic", mqtt.ATTR_PAYLOAD_TEMPLATE: "{{ 1 | bad }}"},
        blocking=True,
    )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_payload_doesnt_render_template(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with unrendered template.

    If both 'payload' and 'payload_template' are provided then fail.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
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


async def test_service_call_with_ascii_qos_retain_flags(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the service call with args that can be misinterpreted.

    Empty payload message and ascii formatted qos and retain flags.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
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


async def test_publish_function_with_bad_encoding_conditions(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test internal publish function with basic use cases."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_publish(
        hass, "some-topic", "test-payload", qos=0, retain=False, encoding=None
    )
    assert (
        "Can't pass-through payload for publishing test-payload on some-topic with no encoding set, need 'bytes' got <class 'str'>"
        in caplog.text
    )
    caplog.clear()
    await mqtt.async_publish(
        hass,
        "some-topic",
        "test-payload",
        qos=0,
        retain=False,
        encoding="invalid_encoding",
    )
    assert (
        "Can't encode payload for publishing test-payload on some-topic with encoding invalid_encoding"
        in caplog.text
    )


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
    # We enforce this because mosquitto does: https://github.com/eclipse/mosquitto/commit/94fdc9cb44c829ff79c74e1daa6f7d04283dfffd
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\u0001")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\u001F")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\u007F")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\u009F")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\ufdd0")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\ufdef")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\ufffe")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\ufffe")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\uffff")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\U0001fffe")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\U0001ffff")


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
    MQTT_ENTITY_DEVICE_INFO_SCHEMA(
        {"connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]]}
    )
    # full device info
    MQTT_ENTITY_DEVICE_INFO_SCHEMA(
        {
            "identifiers": ["helloworld", "hello"],
            "connections": [
                [dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"],
                [dr.CONNECTION_ZIGBEE, "zigbee_id"],
            ],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
            "configuration_url": "http://example.com",
        }
    )
    # full device info with via_device
    MQTT_ENTITY_DEVICE_INFO_SCHEMA(
        {
            "identifiers": ["helloworld", "hello"],
            "connections": [
                [dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"],
                [dr.CONNECTION_ZIGBEE, "zigbee_id"],
            ],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
            "via_device": "test-hub",
            "configuration_url": "http://example.com",
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

    # not an valid URL
    with pytest.raises(vol.Invalid):
        MQTT_ENTITY_DEVICE_INFO_SCHEMA(
            {
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
                "configuration_url": "fake://link",
            }
        )


async def test_receiving_non_utf8_message_gets_logged(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls, caplog
):
    """Test receiving a non utf8 encoded message."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", b"\x9a")

    await hass.async_block_till_done()
    assert (
        "Can't decode payload b'\\x9a' on test-topic with encoding utf-8" in caplog.text
    )


async def test_all_subscriptions_run_when_decode_fails(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test all other subscriptions still run when decode fails for one."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic", record_calls, encoding="ascii")
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", TEMP_CELSIUS)

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of a topic."""
    await mqtt_mock_entry_no_yaml_config()
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

    # Cannot unsubscribe twice
    with pytest.raises(HomeAssistantError):
        unsub()


async def test_subscribe_topic_non_async(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of a topic using the non-async function."""
    await mqtt_mock_entry_no_yaml_config()
    unsub = await hass.async_add_executor_job(
        mqtt.subscribe, hass, "test-topic", record_calls
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic"
    assert calls[0][0].payload == "test-payload"

    await hass.async_add_executor_job(unsub)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_bad_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of a topic."""
    await mqtt_mock_entry_no_yaml_config()
    with pytest.raises(HomeAssistantError):
        await mqtt.async_subscribe(hass, 55, record_calls)


async def test_subscribe_deprecated(hass, mqtt_mock_entry_no_yaml_config):
    """Test the subscription of a topic using deprecated callback signature."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()

    @callback
    def record_calls(topic, payload, qos):
        """Record calls."""
        calls.append((topic, payload, qos))

    calls = []
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
    mqtt_mock.async_publish.reset_mock()

    # Test with partial wrapper
    calls = []
    unsub = await mqtt.async_subscribe(
        hass, "test-topic", RecordCallsPartial(record_calls)
    )

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0] == "test-topic"
    assert calls[0][1] == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_deprecated_async(hass, mqtt_mock_entry_no_yaml_config):
    """Test the subscription of a topic using deprecated coroutine signature."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()

    def async_record_calls(topic, payload, qos):
        """Record calls."""
        calls.append((topic, payload, qos))

    calls = []
    unsub = await mqtt.async_subscribe(hass, "test-topic", async_record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0] == "test-topic"
    assert calls[0][1] == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    mqtt_mock.async_publish.reset_mock()

    # Test with partial wrapper
    calls = []
    unsub = await mqtt.async_subscribe(
        hass, "test-topic", RecordCallsPartial(async_record_calls)
    )

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0] == "test-topic"
    assert calls[0][1] == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_topic_not_match(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test if subscribed topic is not a match."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic/+/on", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic/bier/on"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_no_subtree_match(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic/+/on", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_root_topic_no_subtree_match(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic-123", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_subtree_wildcard_subtree_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic/bier/on"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_subtree_wildcard_root_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "test-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_subtree_wildcard_no_match(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_and_wildcard_root_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "hi/test-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_and_wildcard_subtree_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/test-topic/here-iam", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "hi/test-topic/here-iam"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_and_wildcard_level_no_match(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/here-iam/test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_and_wildcard_no_match(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_sys_root(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of $ root topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "$test-topic/subtree/on", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/subtree/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "$test-topic/subtree/on"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_sys_root_and_wildcard_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of $ root and wildcard topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "$test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/some-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "$test-topic/some-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_topic_sys_root_and_wildcard_subtree_topic(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription of $ root and wildcard subtree topics."""
    await mqtt_mock_entry_no_yaml_config()
    await mqtt.async_subscribe(hass, "$test-topic/subtree/#", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/subtree/some-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == "$test-topic/subtree/some-topic"
    assert calls[0][0].payload == "test-payload"


async def test_subscribe_special_characters(
    hass, mqtt_mock_entry_no_yaml_config, calls, record_calls
):
    """Test the subscription to topics with special characters."""
    await mqtt_mock_entry_no_yaml_config()
    topic = "/test-topic/$(.)[^]{-}"
    payload = "p4y.l[]a|> ?"

    await mqtt.async_subscribe(hass, topic, record_calls)

    async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0][0].topic == topic
    assert calls[0][0].payload == payload


async def test_subscribe_same_topic(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """
    Test subscring to same topic twice and simulate retained messages.

    When subscribing to the same topic again, SUBSCRIBE must be sent to the broker again
    for it to resend any retained messages.
    """
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()

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
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test not calling unsubscribe() when other subscribers are active."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test/state", None)
    await mqtt.async_subscribe(hass, "test/state", None)
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.called

    unsub()
    await hass.async_block_till_done()
    assert not mqtt_client_mock.unsubscribe.called


async def test_unsubscribe_race(hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config):
    """Test not calling unsubscribe() when other subscribers are active."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a = MagicMock()
    calls_b = MagicMock()

    mqtt_client_mock.reset_mock()
    unsub = await mqtt.async_subscribe(hass, "test/state", calls_a)
    unsub()
    await mqtt.async_subscribe(hass, "test/state", calls_b)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test/state", "online")
    await hass.async_block_till_done()
    assert not calls_a.called
    assert calls_b.called

    # We allow either calls [subscribe, unsubscribe, subscribe] or [subscribe, subscribe]
    expected_calls_1 = [
        call.subscribe("test/state", 0),
        call.unsubscribe("test/state"),
        call.subscribe("test/state", 0),
    ]
    expected_calls_2 = [
        call.subscribe("test/state", 0),
        call.subscribe("test/state", 0),
    ]
    assert mqtt_client_mock.mock_calls in (expected_calls_1, expected_calls_2)


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
async def test_restore_subscriptions_on_reconnect(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test subscriptions are restored on reconnect."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    # Fake that the client is connected
    mqtt_mock().connected = True

    await mqtt.async_subscribe(hass, "test/state", None)
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.call_count == 1

    mqtt_client_mock.on_disconnect(None, None, 0)
    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0):
        mqtt_client_mock.on_connect(None, None, None, 0)
        await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.call_count == 2


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
async def test_restore_all_active_subscriptions_on_reconnect(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test active subscriptions are restored correctly on reconnect."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
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

    mqtt_client_mock.on_disconnect(None, None, 0)
    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0):
        mqtt_client_mock.on_connect(None, None, None, 0)
        await hass.async_block_till_done()

    expected.append(call("test/state", 1))
    assert mqtt_client_mock.subscribe.mock_calls == expected


async def test_initial_setup_logs_error(
    hass, caplog, mqtt_client_mock, empty_mqtt_config
):
    """Test for setup failure if initial client connection fails."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)
    mqtt_client_mock.connect.return_value = 1
    try:
        assert await mqtt.async_setup_entry(hass, entry)
        await hass.async_block_till_done()
    except HomeAssistantError:
        assert True
    assert "Failed to connect to MQTT server:" in caplog.text


async def test_logs_error_if_no_connect_broker(
    hass, caplog, mqtt_mock_entry_no_yaml_config, mqtt_client_mock
):
    """Test for setup failure if connection to broker is missing."""
    await mqtt_mock_entry_no_yaml_config()
    # test with rc = 3 -> broker unavailable
    mqtt_client_mock.on_connect(mqtt_client_mock, None, None, 3)
    await hass.async_block_till_done()
    assert (
        "Unable to connect to the MQTT broker: Connection Refused: broker unavailable."
        in caplog.text
    )


@patch("homeassistant.components.mqtt.client.TIMEOUT_ACK", 0.3)
async def test_handle_mqtt_on_callback(
    hass, caplog, mqtt_mock_entry_no_yaml_config, mqtt_client_mock
):
    """Test receiving an ACK callback before waiting for it."""
    await mqtt_mock_entry_no_yaml_config()
    # Simulate an ACK for mid == 1, this will call mqtt_mock._mqtt_handle_mid(mid)
    mqtt_client_mock.on_publish(mqtt_client_mock, None, 1)
    await hass.async_block_till_done()
    # Make sure the ACK has been received
    await hass.async_block_till_done()
    # Now call publish without call back, this will call _wait_for_mid(msg_info.mid)
    await mqtt.async_publish(hass, "no_callback/test-topic", "test-payload")
    # Since the mid event was already set, we should not see any timeout
    await hass.async_block_till_done()
    assert (
        "Transmitting message on no_callback/test-topic: 'test-payload', mid: 1"
        in caplog.text
    )
    assert "No ACK from MQTT server" not in caplog.text


async def test_publish_error(hass, caplog):
    """Test publish error."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)

    # simulate an Out of memory error
    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = lambda *args: 1
        mock_client().publish().rc = 1
        assert await mqtt.async_setup_entry(hass, entry)
        await hass.async_block_till_done()
        with pytest.raises(HomeAssistantError):
            await mqtt.async_publish(
                hass, "some-topic", b"test-payload", qos=0, retain=False, encoding=None
            )
        assert "Failed to connect to MQTT server: Out of memory." in caplog.text


async def test_subscribe_error(
    hass, caplog, mqtt_mock_entry_no_yaml_config, mqtt_client_mock
):
    """Test publish error."""
    await mqtt_mock_entry_no_yaml_config()
    mqtt_client_mock.on_connect(mqtt_client_mock, None, None, 0)
    await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError):
        # simulate client is not connected error before subscribing
        mqtt_client_mock.subscribe.side_effect = lambda *args: (4, None)
        await mqtt.async_subscribe(hass, "some-topic", lambda *args: 0)
        await hass.async_block_till_done()


async def test_handle_message_callback(
    hass, caplog, mqtt_mock_entry_no_yaml_config, mqtt_client_mock
):
    """Test for handling an incoming message callback."""
    await mqtt_mock_entry_no_yaml_config()
    msg = ReceiveMessage("some-topic", b"test-payload", 0, False)
    mqtt_client_mock.on_connect(mqtt_client_mock, None, None, 0)
    await mqtt.async_subscribe(hass, "some-topic", lambda *args: 0)
    mqtt_client_mock.on_message(mock_mqtt, None, msg)

    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "Received message on some-topic: b'test-payload'" in caplog.text


async def test_setup_override_configuration(hass, caplog, tmp_path):
    """Test override setup from configuration entry."""
    calls_username_password_set = []

    def mock_usename_password_set(username, password):
        calls_username_password_set.append((username, password))

    # Mock password setup from config
    config = {
        "username": "someuser",
        "password": "someyamlconfiguredpassword",
        "protocol": "3.1",
    }
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump({mqtt.DOMAIN: config})
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        # Mock config entry
        entry = MockConfigEntry(
            domain=mqtt.DOMAIN,
            data={mqtt.CONF_BROKER: "test-broker", "password": "somepassword"},
        )
        entry.add_to_hass(hass)

        with patch("paho.mqtt.client.Client") as mock_client:
            mock_client().username_pw_set = mock_usename_password_set
            mock_client.on_connect(return_value=0)
            await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: config})
            await entry.async_setup(hass)
            await hass.async_block_till_done()

            assert (
                "Deprecated configuration settings found in configuration.yaml. "
                "These settings from your configuration entry will override:"
                in caplog.text
            )

            # Check if the protocol was set to 3.1 from configuration.yaml
            assert mock_client.call_args[1]["protocol"] == 3

            # Check if the password override worked
            assert calls_username_password_set[0][0] == "someuser"
            assert calls_username_password_set[0][1] == "somepassword"


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_manual_mqtt_with_platform_key(hass, caplog):
    """Test set up a manual MQTT item with a platform key."""
    config = {"platform": "mqtt", "name": "test", "command_topic": "test-topic"}
    with pytest.raises(AssertionError):
        await help_test_setup_manual_entity_from_yaml(hass, "light", config)
    assert (
        "Invalid config for [mqtt]: [platform] is an invalid option for [mqtt]"
        in caplog.text
    )


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_manual_mqtt_with_invalid_config(hass, caplog):
    """Test set up a manual MQTT item with an invalid config."""
    config = {"name": "test"}
    with pytest.raises(AssertionError):
        await help_test_setup_manual_entity_from_yaml(hass, "light", config)
    assert (
        "Invalid config for [mqtt]: required key not provided @ data['mqtt']['light'][0]['command_topic']."
        " Got None. (See ?, line ?)" in caplog.text
    )


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_manual_mqtt_empty_platform(hass, caplog):
    """Test set up a manual MQTT platform without items."""
    config = []
    await help_test_setup_manual_entity_from_yaml(hass, "light", config)
    assert "voluptuous.error.MultipleInvalid" not in caplog.text


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_mqtt_client_protocol(hass, mqtt_mock_entry_with_yaml_config):
    """Test MQTT client protocol setup."""
    with patch("paho.mqtt.client.Client") as mock_client:
        assert await async_setup_component(
            hass,
            mqtt.DOMAIN,
            {
                mqtt.DOMAIN: {
                    mqtt.config_integration.CONF_PROTOCOL: "3.1",
                }
            },
        )
        mock_client.on_connect(return_value=0)
        await hass.async_block_till_done()

        # check if protocol setup was correctly
        assert mock_client.call_args[1]["protocol"] == 3


@patch("homeassistant.components.mqtt.client.TIMEOUT_ACK", 0.2)
@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_handle_mqtt_timeout_on_callback(hass, caplog):
    """Test publish without receiving an ACK callback."""
    mid = 0

    class FakeInfo:
        """Returns a simulated client publish response."""

        mid = 100
        rc = 0

    with patch("paho.mqtt.client.Client") as mock_client:

        def _mock_ack(topic, qos=0):
            # Handle ACK for subscribe normally
            nonlocal mid
            mid += 1
            mock_client.on_subscribe(0, 0, mid)
            return (0, mid)

        # We want to simulate the publish behaviour MQTT client
        mock_client = mock_client.return_value
        mock_client.publish.return_value = FakeInfo()
        mock_client.subscribe.side_effect = _mock_ack
        mock_client.connect.return_value = 0

        entry = MockConfigEntry(
            domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"}
        )
        entry.add_to_hass(hass)

        # Make sure we are connected correctly
        mock_client.on_connect(mock_client, None, None, 0)
        # Set up the integration
        assert await mqtt.async_setup_entry(hass, entry)
        await hass.async_block_till_done()

        # Now call we publish without simulating and ACK callback
        await mqtt.async_publish(hass, "no_callback/test-topic", "test-payload")
        await hass.async_block_till_done()
        # There is no ACK so we should see a timeout in the log after publishing
        assert len(mock_client.publish.mock_calls) == 1
        assert "No ACK from MQTT server" in caplog.text


async def test_setup_raises_ConfigEntryNotReady_if_no_connect_broker(hass, caplog):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = MagicMock(side_effect=OSError("Connection error"))
        assert await mqtt.async_setup_entry(hass, entry)
        await hass.async_block_till_done()
        assert "Failed to connect to MQTT server due to exception:" in caplog.text


@pytest.mark.parametrize(
    "config, insecure_param",
    [
        ({"certificate": "auto"}, "not set"),
        ({"certificate": "auto", "tls_insecure": False}, False),
        ({"certificate": "auto", "tls_insecure": True}, True),
    ],
)
@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_uses_certificate_on_certificate_set_to_auto_and_insecure(
    hass, config, insecure_param, mqtt_mock_entry_with_yaml_config
):
    """Test setup uses bundled certs when certificate is set to auto and insecure."""
    calls = []
    insecure_check = {"insecure": "not set"}

    def mock_tls_set(certificate, certfile=None, keyfile=None, tls_version=None):
        calls.append((certificate, certfile, keyfile, tls_version))

    def mock_tls_insecure_set(insecure_param):
        insecure_check["insecure"] = insecure_param

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().tls_set = mock_tls_set
        mock_client().tls_insecure_set = mock_tls_insecure_set
        assert await async_setup_component(
            hass,
            mqtt.DOMAIN,
            {mqtt.DOMAIN: config},
        )
        await hass.async_block_till_done()

        assert calls

        import certifi

        expectedCertificate = certifi.where()
        assert calls[0][0] == expectedCertificate

        # test if insecure is set
        assert insecure_check["insecure"] == insecure_param


async def test_tls_version(hass, mqtt_mock_entry_with_yaml_config):
    """Test setup defaults for tls."""
    calls = []

    def mock_tls_set(certificate, certfile=None, keyfile=None, tls_version=None):
        calls.append((certificate, certfile, keyfile, tls_version))

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().tls_set = mock_tls_set
        assert await async_setup_component(
            hass,
            mqtt.DOMAIN,
            {mqtt.DOMAIN: {"certificate": "auto"}},
        )
        await hass.async_block_till_done()

        assert calls
        assert calls[0][3] == ssl.PROTOCOL_TLS


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "birth",
                mqtt.ATTR_PAYLOAD: "birth",
                mqtt.ATTR_QOS: 0,
                mqtt.ATTR_RETAIN: False,
            },
        }
    ],
)
async def test_custom_birth_message(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test sending birth message."""
    await mqtt_mock_entry_no_yaml_config()
    birth = asyncio.Event()

    async def wait_birth(topic, payload, qos):
        """Handle birth message."""
        birth.set()

    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.1):
        await mqtt.async_subscribe(hass, "birth", wait_birth)
        mqtt_client_mock.on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await birth.wait()
        mqtt_client_mock.publish.assert_called_with("birth", "birth", 0, False)


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "homeassistant/status",
                mqtt.ATTR_PAYLOAD: "online",
                mqtt.ATTR_QOS: 0,
                mqtt.ATTR_RETAIN: False,
            },
        }
    ],
)
async def test_default_birth_message(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test sending birth message."""
    await mqtt_mock_entry_no_yaml_config()
    birth = asyncio.Event()

    async def wait_birth(topic, payload, qos):
        """Handle birth message."""
        birth.set()

    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.1):
        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        mqtt_client_mock.on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await birth.wait()
        mqtt_client_mock.publish.assert_called_with(
            "homeassistant/status", "online", 0, False
        )


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_BIRTH_MESSAGE: {}}],
)
async def test_no_birth_message(hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config):
    """Test disabling birth message."""
    await mqtt_mock_entry_no_yaml_config()
    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.1):
        mqtt_client_mock.on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await asyncio.sleep(0.2)
        mqtt_client_mock.publish.assert_not_called()


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "homeassistant/status",
                mqtt.ATTR_PAYLOAD: "online",
                mqtt.ATTR_QOS: 0,
                mqtt.ATTR_RETAIN: False,
            },
        }
    ],
)
async def test_delayed_birth_message(
    hass, mqtt_client_mock, mqtt_config_entry_data, mqtt_mock_entry_no_yaml_config
):
    """Test sending birth message does not happen until Home Assistant starts."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()

    hass.state = CoreState.starting
    birth = asyncio.Event()

    await hass.async_block_till_done()

    entry = MockConfigEntry(domain=mqtt.DOMAIN, data=mqtt_config_entry_data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mqtt_component_mock = MagicMock(
        return_value=hass.data["mqtt"],
        spec_set=hass.data["mqtt"],
        wraps=hass.data["mqtt"],
    )
    mqtt_component_mock._mqttc = mqtt_client_mock

    hass.data["mqtt"] = mqtt_component_mock
    mqtt_mock = hass.data["mqtt"]
    mqtt_mock.reset_mock()

    async def wait_birth(topic, payload, qos):
        """Handle birth message."""
        birth.set()

    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.1):
        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        mqtt_client_mock.on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(birth.wait(), 0.2)
        assert not mqtt_client_mock.publish.called
        assert not birth.is_set()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await birth.wait()
        mqtt_client_mock.publish.assert_called_with(
            "homeassistant/status", "online", 0, False
        )


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_WILL_MESSAGE: {
                mqtt.ATTR_TOPIC: "death",
                mqtt.ATTR_PAYLOAD: "death",
                mqtt.ATTR_QOS: 0,
                mqtt.ATTR_RETAIN: False,
            },
        }
    ],
)
async def test_custom_will_message(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test will message."""
    await mqtt_mock_entry_no_yaml_config()

    mqtt_client_mock.will_set.assert_called_with(
        topic="death", payload="death", qos=0, retain=False
    )


async def test_default_will_message(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test will message."""
    await mqtt_mock_entry_no_yaml_config()

    mqtt_client_mock.will_set.assert_called_with(
        topic="homeassistant/status", payload="offline", qos=0, retain=False
    )


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_WILL_MESSAGE: {}}],
)
async def test_no_will_message(hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config):
    """Test will message."""
    await mqtt_mock_entry_no_yaml_config()

    mqtt_client_mock.will_set.assert_not_called()


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {},
            mqtt.CONF_DISCOVERY: False,
        }
    ],
)
async def test_mqtt_subscribes_topics_on_connect(
    hass, mqtt_client_mock, mqtt_mock_entry_no_yaml_config
):
    """Test subscription to topic on connect."""
    await mqtt_mock_entry_no_yaml_config()

    await mqtt.async_subscribe(hass, "topic/test", None)
    await mqtt.async_subscribe(hass, "home/sensor", None, 2)
    await mqtt.async_subscribe(hass, "still/pending", None)
    await mqtt.async_subscribe(hass, "still/pending", None, 1)

    hass.add_job = MagicMock()
    mqtt_client_mock.on_connect(None, None, 0, 0)

    await hass.async_block_till_done()

    assert mqtt_client_mock.disconnect.call_count == 0

    assert len(hass.add_job.mock_calls) == 1
    assert set(hass.add_job.mock_calls[0][1][1]) == {
        ("home/sensor", 2),
        ("still/pending", 1),
        ("topic/test", 0),
    }


async def test_setup_entry_with_config_override(
    hass, device_reg, mqtt_mock_entry_with_yaml_config
):
    """Test if the MQTT component loads with no config and config entry can be setup."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    # mqtt present in yaml config
    assert await async_setup_component(hass, mqtt.DOMAIN, {})
    await hass.async_block_till_done()

    # User sets up a config entry
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Discover a device to verify the entry was setup correctly
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is not None


async def test_update_incomplete_entry(
    hass: HomeAssistant, device_reg, mqtt_client_mock, caplog
):
    """Test if the MQTT component loads when config entry data is incomplete."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    # Config entry data is incomplete
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={"port": 1234})
    entry.add_to_hass(hass)
    # Mqtt present in yaml config
    config = {"broker": "yaml_broker"}
    await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: config})
    await hass.async_block_till_done()

    # Config entry data should now be updated
    assert entry.data == {
        "port": 1234,
        "broker": "yaml_broker",
    }
    # Warnings about broker deprecated, but not about other keys with default values
    assert (
        "The 'broker' option is deprecated, please remove it from your configuration"
        in caplog.text
    )

    # Discover a device to verify the entry was setup correctly
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is not None


async def test_fail_no_broker(hass, device_reg, mqtt_client_mock, caplog):
    """Test if the MQTT component loads when broker configuration is missing."""
    # Config entry data is incomplete
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert "MQTT broker is not configured, please configure it" in caplog.text


@pytest.mark.no_fail_on_log_exception
async def test_message_callback_exception_gets_logged(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test exception raised by message handler."""
    await mqtt_mock_entry_no_yaml_config()

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


async def test_mqtt_ws_subscription(
    hass, hass_ws_client, mqtt_mock_entry_no_yaml_config
):
    """Test MQTT websocket subscription."""
    await mqtt_mock_entry_no_yaml_config()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/subscribe", "topic": "test-topic"})
    response = await client.receive_json()
    assert response["success"]

    async_fire_mqtt_message(hass, "test-topic", "test1")
    async_fire_mqtt_message(hass, "test-topic", "test2")
    async_fire_mqtt_message(hass, "test-topic", b"\xDE\xAD\xBE\xEF")

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "test1"

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "test2"

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "b'\\xde\\xad\\xbe\\xef'"

    # Unsubscribe
    await client.send_json({"id": 8, "type": "unsubscribe_events", "subscription": 5})
    response = await client.receive_json()
    assert response["success"]


async def test_mqtt_ws_subscription_not_admin(
    hass, hass_ws_client, mqtt_mock_entry_no_yaml_config, hass_read_only_access_token
):
    """Test MQTT websocket user is not admin."""
    await mqtt_mock_entry_no_yaml_config()
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json({"id": 5, "type": "mqtt/subscribe", "topic": "test-topic"})
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unauthorized"
    assert response["error"]["message"] == "Unauthorized"


async def test_dump_service(hass, mqtt_mock_entry_no_yaml_config):
    """Test that we can dump a topic."""
    await mqtt_mock_entry_no_yaml_config()
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
    hass, device_reg, entity_reg, hass_ws_client, mqtt_mock_entry_no_yaml_config
):
    """Test MQTT websocket device removal."""
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

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
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    await client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mqtt_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Verify device entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is None


async def test_mqtt_ws_get_device_debug_info(
    hass, device_reg, hass_ws_client, mqtt_mock_entry_no_yaml_config
):
    """Test MQTT websocket device debug info."""
    await mqtt_mock_entry_no_yaml_config()
    config_sensor = {
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "state_topic": "foobar/sensor",
        "unique_id": "unique",
    }
    config_trigger = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "topic": "test-topic1",
        "type": "foo",
        "subtype": "bar",
    }
    data_sensor = json.dumps(config_sensor)
    data_trigger = json.dumps(config_trigger)

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data_sensor)
    async_fire_mqtt_message(
        hass, "homeassistant/device_automation/bla/config", data_trigger
    )
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
                    "payload": config_sensor,
                    "topic": "homeassistant/sensor/bla/config",
                },
                "transmitted": [],
            }
        ],
        "triggers": [
            {
                "discovery_data": {
                    "payload": config_trigger,
                    "topic": "homeassistant/device_automation/bla/config",
                },
                "trigger_key": ["device_automation", "bla"],
            }
        ],
    }
    assert response["result"] == expected_result


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.CAMERA])
async def test_mqtt_ws_get_device_debug_info_binary(
    hass, device_reg, hass_ws_client, mqtt_mock_entry_no_yaml_config
):
    """Test MQTT websocket device debug info."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "topic": "foobar/image",
        "unique_id": "unique",
    }
    data = json.dumps(config)

    async_fire_mqtt_message(hass, "homeassistant/camera/bla/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is not None

    small_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x04\x00\x00\x00\x04\x08\x06"
        b"\x00\x00\x00\xa9\xf1\x9e~\x00\x00\x00\x13IDATx\xdac\xfc\xcf\xc0P\xcf\x80\x04"
        b"\x18I\x17\x00\x00\xf2\xae\x05\xfdR\x01\xc2\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    async_fire_mqtt_message(hass, "foobar/image", small_png)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/device/debug_info", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]
    expected_result = {
        "entities": [
            {
                "entity_id": "camera.mqtt_camera",
                "subscriptions": [
                    {
                        "topic": "foobar/image",
                        "messages": [
                            {
                                "payload": str(small_png),
                                "qos": 0,
                                "retain": False,
                                "time": ANY,
                                "topic": "foobar/image",
                            }
                        ],
                    }
                ],
                "discovery_data": {
                    "payload": config,
                    "topic": "homeassistant/camera/bla/config",
                },
                "transmitted": [],
            }
        ],
        "triggers": [],
    }
    assert response["result"] == expected_result


async def test_debug_info_multiple_devices(hass, mqtt_mock_entry_no_yaml_config):
    """Test we get correct debug_info when multiple devices are present."""
    await mqtt_mock_entry_no_yaml_config()
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

    registry = dr.async_get(hass)

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

        debug_info_data = debug_info.info_for_device(hass, device.id)
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


async def test_debug_info_multiple_entities_triggers(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test we get correct debug_info for a device with multiple entities and triggers."""
    await mqtt_mock_entry_no_yaml_config()
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

    registry = dr.async_get(hass)

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
    debug_info_data = debug_info.info_for_device(hass, device.id)
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


async def test_debug_info_non_mqtt(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test we get empty debug_info for a device with non MQTT entities."""
    await mqtt_mock_entry_no_yaml_config()
    DOMAIN = "sensor"
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in DEVICE_CLASSES:
        entity_reg.async_get_or_create(
            DOMAIN,
            "test",
            platform.ENTITIES[device_class].unique_id,
            device_id=device_entry.id,
        )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "test"}})

    debug_info_data = debug_info.info_for_device(hass, device_entry.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 0


async def test_debug_info_wildcard(hass, mqtt_mock_entry_no_yaml_config):
    """Test debug info."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        async_fire_mqtt_message(hass, "sensor/abc", "123")

    debug_info_data = debug_info.info_for_device(hass, device.id)
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


async def test_debug_info_filter_same(hass, mqtt_mock_entry_no_yaml_config):
    """Test debug info removes messages with same timestamp."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
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

    debug_info_data = debug_info.info_for_device(hass, device.id)
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


async def test_debug_info_same_topic(hass, mqtt_mock_entry_no_yaml_config):
    """Test debug info."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/status",
        "availability_topic": "sensor/status",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/status", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        async_fire_mqtt_message(hass, "sensor/status", "123", qos=0, retain=False)

    debug_info_data = debug_info.info_for_device(hass, device.id)
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


async def test_debug_info_qos_retain(hass, mqtt_mock_entry_no_yaml_config):
    """Test debug info."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "platform": "mqtt",
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
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

    debug_info_data = debug_info.info_for_device(hass, device.id)
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


async def test_publish_json_from_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test the publishing of call to services."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()

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


async def test_subscribe_connection_status(
    hass, mqtt_mock_entry_no_yaml_config, mqtt_client_mock
):
    """Test connextion status subscription."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    mqtt_connected_calls = []

    @callback
    async def async_mqtt_connected(status):
        """Update state on connection/disconnection to MQTT broker."""
        mqtt_connected_calls.append(status)

    mqtt_mock.connected = True

    unsub = mqtt.async_subscribe_connection_status(hass, async_mqtt_connected)
    await hass.async_block_till_done()

    # Mock connection status
    mqtt_client_mock.on_connect(None, None, 0, 0)
    await hass.async_block_till_done()
    assert mqtt.is_connected(hass) is True

    # Mock disconnect status
    mqtt_client_mock.on_disconnect(None, None, 0)
    await hass.async_block_till_done()

    # Unsubscribe
    unsub()

    mqtt_client_mock.on_connect(None, None, 0, 0)
    await hass.async_block_till_done()

    # Check calls
    assert len(mqtt_connected_calls) == 2
    assert mqtt_connected_calls[0] is True
    assert mqtt_connected_calls[1] is False


async def test_one_deprecation_warning_per_platform(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test a deprecation warning is is logged once per platform."""
    platform = "light"
    config = {"platform": "mqtt", "command_topic": "test-topic"}
    config1 = copy.deepcopy(config)
    config1["name"] = "test1"
    config2 = copy.deepcopy(config)
    config2["name"] = "test2"
    await async_setup_component(hass, platform, {platform: [config1, config2]})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    count = 0
    for record in caplog.records:
        if record.levelname == "WARNING" and (
            f"Manually configured MQTT {platform}(s) found under platform key '{platform}'"
            in record.message
        ):
            count += 1
    assert count == 1


async def test_config_schema_validation(hass):
    """Test invalid platform options in the config schema do not pass the config validation."""
    config = {"mqtt": {"sensor": [{"some_illegal_topic": "mystate/topic/path"}]}}
    with pytest.raises(vol.MultipleInvalid):
        CONFIG_SCHEMA(config)


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
async def test_unload_config_entry(
    hass, mqtt_mock, mqtt_client_mock, tmp_path, caplog
) -> None:
    """Test unloading the MQTT entry."""
    assert hass.services.has_service(mqtt.DOMAIN, "dump")
    assert hass.services.has_service(mqtt.DOMAIN, "publish")

    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED

    # Publish just before unloading to test await cleanup
    mqtt_client_mock.reset_mock()
    mqtt.publish(hass, "just_in_time", "published", qos=0, retain=False)

    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump({})
    new_yaml_config_file.write_text(new_yaml_config)
    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        assert await hass.config_entries.async_unload(mqtt_config_entry.entry_id)
        mqtt_client_mock.publish.assert_any_call("just_in_time", "published", 0, False)
        assert mqtt_config_entry.state is ConfigEntryState.NOT_LOADED
        await hass.async_block_till_done()
    assert not hass.services.has_service(mqtt.DOMAIN, "dump")
    assert not hass.services.has_service(mqtt.DOMAIN, "publish")
    assert "No ACK from MQTT server" not in caplog.text


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_with_disabled_entry(hass, caplog) -> None:
    """Test setting up the platform with a disabled config entry."""
    # Try to setup the platform with a disabled config entry
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN, data={}, disabled_by=ConfigEntryDisabler.USER
    )
    config_entry.add_to_hass(hass)

    config = {mqtt.DOMAIN: {}}
    await async_setup_component(hass, mqtt.DOMAIN, config)
    await hass.async_block_till_done()

    assert "MQTT will be not available until the config entry is enabled" in caplog.text


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_publish_or_subscribe_without_valid_config_entry(hass, caplog):
    """Test internal publish function with bas use cases."""
    with pytest.raises(HomeAssistantError):
        await mqtt.async_publish(
            hass, "some-topic", "test-payload", qos=0, retain=False, encoding=None
        )
    with pytest.raises(HomeAssistantError):
        await mqtt.async_subscribe(hass, "some-topic", lambda: None, qos=0)


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
async def test_reload_entry_with_new_config(hass, tmp_path):
    """Test reloading the config entry with a new yaml config."""
    config_old = [{"name": "test_old1", "command_topic": "test-topic_old"}]
    config_yaml_new = {
        "mqtt": {
            "light": [{"name": "test_new_modern", "command_topic": "test-topic_new"}]
        },
        "light": [
            {
                "platform": "mqtt",
                "name": "test_new_legacy",
                "command_topic": "test-topic_new",
            }
        ],
    }
    await help_test_setup_manual_entity_from_yaml(hass, "light", config_old)
    assert hass.states.get("light.test_old1") is not None

    await help_test_entry_reload_with_new_config(hass, tmp_path, config_yaml_new)
    assert hass.states.get("light.test_old1") is None
    assert hass.states.get("light.test_new_modern") is not None
    assert hass.states.get("light.test_new_legacy") is not None


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
async def test_disabling_and_enabling_entry(hass, tmp_path, caplog):
    """Test disabling and enabling the config entry."""
    config_old = [{"name": "test_old1", "command_topic": "test-topic_old"}]
    config_yaml_new = {
        "mqtt": {
            "light": [{"name": "test_new_modern", "command_topic": "test-topic_new"}]
        },
        "light": [
            {
                "platform": "mqtt",
                "name": "test_new_legacy",
                "command_topic": "test-topic_new",
            }
        ],
    }
    await help_test_setup_manual_entity_from_yaml(hass, "light", config_old)
    assert hass.states.get("light.test_old1") is not None

    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    assert mqtt_config_entry.state is ConfigEntryState.LOADED
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump(config_yaml_new)
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file), patch(
        "paho.mqtt.client.Client"
    ) as mock_client:
        mock_client().connect = lambda *args: 0

        # Late discovery of a light
        config = '{"name": "abc", "command_topic": "test-topic"}'
        async_fire_mqtt_message(hass, "homeassistant/light/abc/config", config)

        # Disable MQTT config entry
        await hass.config_entries.async_set_disabled_by(
            mqtt_config_entry.entry_id, ConfigEntryDisabler.USER
        )

        await hass.async_block_till_done()
        await hass.async_block_till_done()
        # Assert that the discovery was still received
        # but kipped the setup
        assert (
            "MQTT integration is disabled, skipping setup of manually configured MQTT light"
            in caplog.text
        )

        assert mqtt_config_entry.state is ConfigEntryState.NOT_LOADED
        assert hass.states.get("light.test_old1") is None

        # Enable the entry again
        await hass.config_entries.async_set_disabled_by(
            mqtt_config_entry.entry_id, None
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert mqtt_config_entry.state is ConfigEntryState.LOADED

        assert hass.states.get("light.test_old1") is None
        assert hass.states.get("light.test_new_modern") is not None
        assert hass.states.get("light.test_new_legacy") is not None


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
@pytest.mark.parametrize(
    "config, unique",
    [
        (
            [
                {
                    "name": "test1",
                    "unique_id": "very_not_unique_deadbeef",
                    "command_topic": "test-topic_unique",
                },
                {
                    "name": "test2",
                    "unique_id": "very_not_unique_deadbeef",
                    "command_topic": "test-topic_unique",
                },
            ],
            False,
        ),
        (
            [
                {
                    "name": "test1",
                    "unique_id": "very_unique_deadbeef1",
                    "command_topic": "test-topic_unique",
                },
                {
                    "name": "test2",
                    "unique_id": "very_unique_deadbeef2",
                    "command_topic": "test-topic_unique",
                },
            ],
            True,
        ),
    ],
)
async def test_setup_manual_items_with_unique_ids(
    hass, tmp_path, caplog, config, unique
):
    """Test setup manual items is generating unique id's."""
    await help_test_setup_manual_entity_from_yaml(hass, "light", config)

    assert hass.states.get("light.test1") is not None
    assert (hass.states.get("light.test2") is not None) == unique
    assert bool("Platform mqtt does not generate unique IDs." in caplog.text) != unique

    # reload and assert again
    caplog.clear()
    await help_test_entry_reload_with_new_config(
        hass, tmp_path, {"mqtt": {"light": config}}
    )

    assert hass.states.get("light.test1") is not None
    assert (hass.states.get("light.test2") is not None) == unique
    assert bool("Platform mqtt does not generate unique IDs." in caplog.text) != unique


async def test_remove_unknown_conf_entry_options(hass, mqtt_client_mock, caplog):
    """Test unknown keys in config entry data is removed."""
    mqtt_config_entry_data = {
        mqtt.CONF_BROKER: "mock-broker",
        mqtt.CONF_BIRTH_MESSAGE: {},
        mqtt.client.CONF_PROTOCOL: mqtt.const.PROTOCOL_311,
    }

    entry = MockConfigEntry(
        data=mqtt_config_entry_data,
        domain=mqtt.DOMAIN,
        title="MQTT",
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert mqtt.client.CONF_PROTOCOL not in entry.data
    assert (
        "The following unsupported configuration options were removed from the "
        "MQTT config entry: {'protocol'}. Add them to configuration.yaml if they "
        "are needed"
    ) in caplog.text
