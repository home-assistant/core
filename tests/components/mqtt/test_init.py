"""The tests for the MQTT component setup and helpers."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from functools import partial
import json
import time
from typing import Any, TypedDict
from unittest.mock import ANY, MagicMock, Mock, mock_open, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant import core as ha
from homeassistant.components import mqtt
from homeassistant.components.mqtt import debug_info
from homeassistant.components.mqtt.models import (
    MessageCallbackType,
    MqttCommandTemplateException,
    MqttValueTemplateException,
    ReceiveMessage,
)
from homeassistant.components.mqtt.schemas import MQTT_ENTITY_DEVICE_INFO_SCHEMA
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, template
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import utcnow

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockEntityPlatform,
    MockMqttReasonCode,
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_restore_cache,
    setup_test_component_platform,
)
from tests.components.sensor.common import MockSensor
from tests.typing import (
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    WebSocketGenerator,
)


class _DebugDeviceInfo(TypedDict, total=False):
    """Debug device info test data type."""

    device: dict[str, Any]
    platform: str
    state_topic: str
    unique_id: str
    type: str
    subtype: str
    automation_type: str
    topic: str


class _DebugInfo(TypedDict):
    """Debug info test data type."""

    domain: str
    config: _DebugDeviceInfo


async def test_command_template_value(hass: HomeAssistant) -> None:
    """Test the rendering of MQTT command template."""

    variables = {"id": 1234, "some_var": "beer"}

    # test rendering value
    tpl = template.Template("{{ value + 1 }}", hass=hass)
    cmd_tpl = mqtt.MqttCommandTemplate(tpl)
    assert cmd_tpl.async_render(4321) == "4322"

    # test variables at rendering
    tpl = template.Template("{{ some_var }}", hass=hass)
    cmd_tpl = mqtt.MqttCommandTemplate(tpl)
    assert cmd_tpl.async_render(None, variables=variables) == "beer"


@pytest.mark.parametrize(
    "config",
    [
        {
            "command_topic": "test/select",
            "name": "Test Select",
            "options": ["milk", "beer"],
            "command_template": '{"option": "{{ value }}", "entity_id": "{{ entity_id }}", "name": "{{ name }}", "this_object_state": "{{ this.state }}"}',
        }
    ],
)
async def test_command_template_variables(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, config: ConfigType
) -> None:
    """Test the rendering of entity variables."""
    topic = "test/select"

    fake_state = ha.State("select.test_select", "milk")
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/select/bla/config", json.dumps(config))
    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state and state.state == "milk"
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
    assert state and state.state == "beer"

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
        assert state and state.state == "milk"


async def test_command_template_fails(hass: HomeAssistant) -> None:
    """Test the exception handling of an MQTT command template."""
    tpl = template.Template("{{ value * 2 }}", hass=hass)
    cmd_tpl = mqtt.MqttCommandTemplate(tpl)
    with pytest.raises(MqttCommandTemplateException) as exc:
        cmd_tpl.async_render(None)
    assert "unsupported operand type(s) for *: 'NoneType' and 'int'" in str(exc.value)


async def test_value_template_value(hass: HomeAssistant) -> None:
    """Test the rendering of MQTT value template."""

    variables = {"id": 1234, "some_var": "beer"}

    # test rendering value
    tpl = template.Template("{{ value_json.id }}", hass=hass)
    val_tpl = mqtt.MqttValueTemplate(tpl)
    assert val_tpl.async_render_with_possible_json_value('{"id": 4321}') == "4321"

    # test variables at rendering
    tpl = template.Template("{{ value_json.id }} {{ some_var }} {{ code }}", hass=hass)
    val_tpl = mqtt.MqttValueTemplate(tpl, config_attributes={"code": 1234})
    assert (
        val_tpl.async_render_with_possible_json_value(
            '{"id": 4321}', variables=variables
        )
        == "4321 beer 1234"
    )

    # test with default value if an error occurs due to an invalid template
    tpl = template.Template("{{ value_json.id | as_datetime }}", hass=hass)
    val_tpl = mqtt.MqttValueTemplate(tpl)
    assert (
        val_tpl.async_render_with_possible_json_value('{"otherid": 4321}', "my default")
        == "my default"
    )

    # test value template with entity
    entity = Entity()
    entity.hass = hass
    entity.platform = MockEntityPlatform(hass)
    entity.entity_id = "select.test"
    tpl = template.Template("{{ value_json.id }}", hass=hass)
    val_tpl = mqtt.MqttValueTemplate(tpl, entity=entity)
    assert val_tpl.async_render_with_possible_json_value('{"id": 4321}') == "4321"

    # test this object in a template
    tpl2 = template.Template("{{ this.entity_id }}", hass=hass)
    val_tpl2 = mqtt.MqttValueTemplate(tpl2, entity=entity)
    assert val_tpl2.async_render_with_possible_json_value("bla") == "select.test"

    with patch(
        "homeassistant.helpers.template.TemplateStateFromEntityId", MagicMock()
    ) as template_state_calls:
        tpl3 = template.Template("{{ this.entity_id }}", hass=hass)
        val_tpl3 = mqtt.MqttValueTemplate(tpl3, entity=entity)
        val_tpl3.async_render_with_possible_json_value("call1")
        val_tpl3.async_render_with_possible_json_value("call2")
        assert template_state_calls.call_count == 1


async def test_value_template_fails(hass: HomeAssistant) -> None:
    """Test the rendering of MQTT value template fails."""
    entity = MockEntity(entity_id="sensor.test")
    entity.hass = hass
    entity.platform = MockEntityPlatform(hass)
    tpl = template.Template("{{ value_json.some_var * 2 }}", hass=hass)
    val_tpl = mqtt.MqttValueTemplate(tpl, entity=entity)
    with pytest.raises(MqttValueTemplateException) as exc:
        val_tpl.async_render_with_possible_json_value('{"some_var": null }')
    assert str(exc.value) == (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' "
        "rendering template for entity 'sensor.test', "
        "template: '{{ value_json.some_var * 2 }}' "
        'and payload: {"some_var": null }'
    )
    with pytest.raises(MqttValueTemplateException) as exc:
        val_tpl.async_render_with_possible_json_value(
            '{"some_var": null }', default="100"
        )
    assert str(exc.value) == (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' "
        "rendering template for entity 'sensor.test', "
        "template: '{{ value_json.some_var * 2 }}', default value: 100 and payload: "
        '{"some_var": null }'
    )


async def test_service_call_without_topic_does_not_publish(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call if topic is missing."""
    mqtt_mock = await mqtt_mock_entry()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {},
            blocking=True,
        )
    assert not mqtt_mock.async_publish.called


async def test_service_call_mqtt_entry_does_not_publish(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test the service call if topic is missing."""
    assert await async_setup_component(hass, mqtt.DOMAIN, {})
    with pytest.raises(
        ServiceValidationError,
        match='Cannot publish to topic "test_topic", make sure MQTT is set up correctly',
    ):
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: "test_topic",
                mqtt.ATTR_PAYLOAD: "payload",
            },
            blocking=True,
        )


async def test_service_call_with_template_topic_renders_invalid_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the action call with rendered, invalid topic template.

    If a wildcard topic is rendered, then fail.
    """
    mqtt_mock = await mqtt_mock_entry()
    with pytest.raises(vol.Invalid) as exc:
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: "test/{{ '+' if True else 'topic' }}/topic",
                mqtt.ATTR_PAYLOAD: "payload",
            },
            blocking=True,
        )
    assert (
        str(exc.value) == "Wildcards cannot be used in topic names "
        "for dictionary value @ data['topic']"
    )
    assert not mqtt_mock.async_publish.called


@pytest.mark.parametrize(
    ("attr_payload", "payload", "evaluate_payload", "literal_eval_calls"),
    [
        ("b'\\xde\\xad\\xbe\\xef'", b"\xde\xad\xbe\xef", True, 1),
        ("b'\\xde\\xad\\xbe\\xef'", "b'\\xde\\xad\\xbe\\xef'", False, 0),
        ("DEADBEEF", "DEADBEEF", False, 0),
        (
            "b'\\xde",
            "b'\\xde",
            True,
            1,
        ),  # Bytes literal is invalid, fall back to string
    ],
)
async def test_mqtt_publish_action_call_with_raw_data(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    attr_payload: str,
    payload: str | bytes,
    evaluate_payload: bool,
    literal_eval_calls: int,
) -> None:
    """Test the mqtt publish action call raw data.

    When `payload` represents a `bytes` object, it should be published
    as raw data if `evaluate_payload` is set.
    """
    mqtt_mock = await mqtt_mock_entry()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {
            mqtt.ATTR_TOPIC: "test/topic",
            mqtt.ATTR_PAYLOAD: attr_payload,
            mqtt.ATTR_EVALUATE_PAYLOAD: evaluate_payload,
        },
        blocking=True,
    )
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] == payload

    with patch(
        "homeassistant.components.mqtt.models.literal_eval"
    ) as literal_eval_mock:
        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: "test/topic",
                mqtt.ATTR_PAYLOAD: attr_payload,
            },
            blocking=True,
        )
        literal_eval_mock.assert_not_called()

        await hass.services.async_call(
            mqtt.DOMAIN,
            mqtt.SERVICE_PUBLISH,
            {
                mqtt.ATTR_TOPIC: "test/topic",
                mqtt.ATTR_PAYLOAD: attr_payload,
                mqtt.ATTR_EVALUATE_PAYLOAD: evaluate_payload,
            },
            blocking=True,
        )
        assert len(literal_eval_mock.mock_calls) == literal_eval_calls


async def test_service_call_with_ascii_qos_retain_flags(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with args that can be misinterpreted.

    Empty payload message and ascii formatted qos and retain flags.
    """
    mqtt_mock = await mqtt_mock_entry()
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
    assert mqtt_mock.async_publish.call_args[0][1] == ""
    assert mqtt_mock.async_publish.call_args[0][2] == 2
    assert not mqtt_mock.async_publish.call_args[0][3]

    mqtt_mock.reset_mock()

    # Test service call without payload
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {
            mqtt.ATTR_TOPIC: "test/topic",
            mqtt.ATTR_QOS: "2",
            mqtt.ATTR_RETAIN: "no",
        },
        blocking=True,
    )
    assert mqtt_mock.async_publish.called
    assert mqtt_mock.async_publish.call_args[0][1] is None
    assert mqtt_mock.async_publish.call_args[0][2] == 2
    assert not mqtt_mock.async_publish.call_args[0][3]


async def test_publish_function_with_bad_encoding_conditions(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test internal publish function with basic use cases."""
    await mqtt_mock_entry()
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


def test_validate_topic() -> None:
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
        mqtt.util.valid_topic("\u001f")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\u007f")
    with pytest.raises(vol.Invalid):
        mqtt.util.valid_topic("\u009f")
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


def test_validate_subscribe_topic() -> None:
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


def test_validate_publish_topic() -> None:
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


def test_entity_device_info_schema() -> None:
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
            "serial_number": "1234deadbeef",
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
            "serial_number": "1234deadbeef",
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

    # not a valid URL
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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "sensor": [
                    {
                        "name": "test-sensor",
                        "unique_id": "test-sensor",
                        "state_topic": "test/state",
                    }
                ]
            }
        }
    ],
)
@pytest.mark.usefixtures("mock_hass_config")
async def test_handle_logging_on_writing_the_entity_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test on log handling when an error occurs writing the state."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "test/state", b"initial_state")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor")
    assert state is not None
    assert state.state == "initial_state"
    with patch(
        "homeassistant.helpers.entity.Entity.async_write_ha_state",
        side_effect=ValueError("Invalid value for sensor"),
    ):
        async_fire_mqtt_message(hass, "test/state", b"payload causing errors")
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_sensor")
        assert state is not None
        assert state.state == "initial_state"
        assert "Invalid value for sensor" in caplog.text
        assert (
            "Exception raised while updating "
            "state of sensor.test_sensor, topic: 'test/state' "
            "with payload: b'payload causing errors'" in caplog.text
        )


async def test_receiving_non_utf8_message_gets_logged(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test receiving a non utf8 encoded message."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", b"\x9a")

    await hass.async_block_till_done()
    assert (
        "Can't decode payload b'\\x9a' on test-topic with encoding utf-8" in caplog.text
    )


async def test_receiving_message_with_non_utf8_topic_gets_logged(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test receiving a non utf8 encoded topic."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    # Local import to avoid processing MQTT modules when running a testcase
    # which does not use MQTT.

    # pylint: disable-next=import-outside-toplevel
    from paho.mqtt.client import MQTTMessage

    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.mqtt.models import MqttData

    msg = MQTTMessage(topic=b"tasmota/discovery/18FE34E0B760\xcc\x02")
    msg.payload = b"Payload"
    msg.qos = 2
    msg.retain = True
    msg.timestamp = time.monotonic()  # type:ignore[assignment]

    mqtt_data: MqttData = hass.data["mqtt"]
    assert mqtt_data.client
    mqtt_data.client._async_mqtt_on_message(Mock(), None, msg)

    assert (
        "Skipping received retained message on invalid "
        "topic b'tasmota/discovery/18FE34E0B760\\xcc\\x02' "
        "(qos=2): b'Payload'" in caplog.text
    )


@pytest.mark.usefixtures("mqtt_client_mock")
async def test_reload_entry_with_restored_subscriptions(
    hass: HomeAssistant,
    mock_debouncer: asyncio.Event,
    record_calls: MessageCallbackType,
    recorded_calls: list[ReceiveMessage],
) -> None:
    """Test reloading the config entry with with subscriptions restored."""
    # Setup the MQTT entry
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={mqtt.CONF_BROKER: "test-broker"},
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    hass.config.components.add(mqtt.DOMAIN)
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        await hass.config_entries.async_setup(entry.entry_id)

    mock_debouncer.clear()
    await mqtt.async_subscribe(hass, "test-topic", record_calls)
    await mqtt.async_subscribe(hass, "wild/+/card", record_calls)
    # cooldown
    await mock_debouncer.wait()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")
    async_fire_mqtt_message(hass, "wild/any/card", "wild-card-payload")

    assert len(recorded_calls) == 2
    assert recorded_calls[0].topic == "test-topic"
    assert recorded_calls[0].payload == "test-payload"
    assert recorded_calls[1].topic == "wild/any/card"
    assert recorded_calls[1].payload == "wild-card-payload"
    recorded_calls.clear()

    # Reload the entry
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        assert await hass.config_entries.async_reload(entry.entry_id)
        mock_debouncer.clear()
        assert entry.state is ConfigEntryState.LOADED
        # cooldown
        await mock_debouncer.wait()

    async_fire_mqtt_message(hass, "test-topic", "test-payload2")
    async_fire_mqtt_message(hass, "wild/any/card", "wild-card-payload2")

    assert len(recorded_calls) == 2
    assert recorded_calls[0].topic == "test-topic"
    assert recorded_calls[0].payload == "test-payload2"
    assert recorded_calls[1].topic == "wild/any/card"
    assert recorded_calls[1].payload == "wild-card-payload2"
    recorded_calls.clear()

    # Reload the entry again
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        assert await hass.config_entries.async_reload(entry.entry_id)
        mock_debouncer.clear()
        assert entry.state is ConfigEntryState.LOADED
        # cooldown
        await mock_debouncer.wait()

    async_fire_mqtt_message(hass, "test-topic", "test-payload3")
    async_fire_mqtt_message(hass, "wild/any/card", "wild-card-payload3")

    assert len(recorded_calls) == 2
    assert recorded_calls[0].topic == "test-topic"
    assert recorded_calls[0].payload == "test-payload3"
    assert recorded_calls[1].topic == "wild/any/card"
    assert recorded_calls[1].payload == "wild-card-payload3"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "light": {
                    "platform": "mqtt",
                    "name": "test",
                    "command_topic": "test-topic",
                }
            }
        }
    ],
)
async def test_setup_manual_mqtt_with_platform_key(
    mqtt_mock_entry: MqttMockHAClientGenerator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test set up a manual MQTT item with a platform key."""
    assert await mqtt_mock_entry()
    assert (
        "extra keys not allowed @ data['platform'] for manually configured MQTT light item"
        in caplog.text
    )


@pytest.mark.parametrize("hass_config", [{mqtt.DOMAIN: {"light": {"name": "test"}}}])
async def test_setup_manual_mqtt_with_invalid_config(
    mqtt_mock_entry: MqttMockHAClientGenerator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test set up a manual MQTT item with an invalid config."""
    assert await mqtt_mock_entry()
    assert "required key not provided" in caplog.text


@pytest.mark.usefixtures("mqtt_client_mock")
async def test_default_entry_setting_are_applied(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test if the MQTT component loads when config entry data not has all default settings."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    # Config entry data is incomplete but valid according the schema
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker", "port": 1234},
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    hass.config.components.add(mqtt.DOMAIN)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Discover a device to verify the entry was setup correctly
    # The discovery prefix should be the default
    # And that the default settings were merged
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None


@pytest.mark.no_fail_on_log_exception
async def test_message_callback_exception_gets_logged(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test exception raised by message handler."""
    await mqtt_mock_entry()

    @callback
    def bad_handler(msg: ReceiveMessage) -> None:
        """Handle callback."""
        raise ValueError("This is a bad message callback")

    await mqtt.async_subscribe(hass, "test-topic", bad_handler)
    async_fire_mqtt_message(hass, "test-topic", "test")
    await hass.async_block_till_done()

    assert (
        "Exception in bad_handler when handling msg on 'test-topic':"
        " 'test'" in caplog.text
    )


@pytest.mark.no_fail_on_log_exception
@pytest.mark.usefixtures("mock_debouncer", "setup_with_birth_msg_client_mock")
async def test_message_partial_callback_exception_gets_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_debouncer: asyncio.Event
) -> None:
    """Test exception raised by message handler."""

    @callback
    def bad_handler(msg: ReceiveMessage) -> None:
        """Handle callback."""
        raise ValueError("This is a bad message callback")

    def parial_handler(
        msg_callback: MessageCallbackType,
        attributes: set[str],
        msg: ReceiveMessage,
    ) -> None:
        """Partial callback handler."""
        msg_callback(msg)

    mock_debouncer.clear()
    await mqtt.async_subscribe(
        hass, "test-topic", partial(parial_handler, bad_handler, {"some_attr"})
    )
    await mock_debouncer.wait()
    async_fire_mqtt_message(hass, "test-topic", "test")
    await hass.async_block_till_done()

    assert (
        "Exception in bad_handler when handling msg on 'test-topic':"
        " 'test'" in caplog.text
    )


async def test_mqtt_ws_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT websocket subscription."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/subscribe", "topic": "test-topic"})
    response = await client.receive_json()
    assert response["success"]

    async_fire_mqtt_message(hass, "test-topic", "test1")
    async_fire_mqtt_message(hass, "test-topic", "test2")
    async_fire_mqtt_message(hass, "test-topic", b"\xde\xad\xbe\xef")

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

    # Subscribe with QoS 2
    await client.send_json(
        {"id": 9, "type": "mqtt/subscribe", "topic": "test-topic", "qos": 2}
    )
    response = await client.receive_json()
    assert response["success"]

    async_fire_mqtt_message(hass, "test-topic", "test1", 2)
    async_fire_mqtt_message(hass, "test-topic", "test2", 2)
    async_fire_mqtt_message(hass, "test-topic", b"\xde\xad\xbe\xef", 2)

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "test1"
    assert response["event"]["qos"] == 2

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "test2"
    assert response["event"]["qos"] == 2

    response = await client.receive_json()
    assert response["event"]["topic"] == "test-topic"
    assert response["event"]["payload"] == "b'\\xde\\xad\\xbe\\xef'"
    assert response["event"]["qos"] == 2

    # Unsubscribe
    await client.send_json({"id": 15, "type": "unsubscribe_events", "subscription": 9})
    response = await client.receive_json()
    assert response["success"]


async def test_mqtt_ws_subscription_not_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test MQTT websocket user is not admin."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json({"id": 5, "type": "mqtt/subscribe", "topic": "test-topic"})
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unauthorized"
    assert response["error"]["message"] == "Unauthorized"


async def test_dump_service(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that we can dump a topic."""
    await mqtt_mock_entry()
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
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT websocket device removal."""
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()
    await mqtt_mock_entry()

    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None

    client = await hass_ws_client(hass)
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    response = await client.remove_device(device_entry.id, mqtt_config_entry.entry_id)
    assert response["success"]

    # Verify device entry is cleared
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None


async def test_mqtt_ws_get_device_debug_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT websocket device debug info."""
    await mqtt_mock_entry()
    config_sensor = {
        "device": {"identifiers": ["0AFFD2"]},
        "state_topic": "foobar/sensor",
        "unique_id": "unique",
    }
    config_trigger = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"]},
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
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
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
                "entity_id": "sensor.none_mqtt_sensor",
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


async def test_mqtt_ws_get_device_debug_info_binary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT websocket device debug info."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["0AFFD2"]},
        "topic": "foobar/image",
        "unique_id": "unique",
    }
    data = json.dumps(config)

    async_fire_mqtt_message(hass, "homeassistant/camera/bla/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
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
                "entity_id": "camera.none_mqtt_camera",
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


async def test_debug_info_multiple_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test we get correct debug_info when multiple devices are present."""
    await mqtt_mock_entry()
    devices: list[_DebugInfo] = [
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

    for dev in devices:
        data = json.dumps(dev["config"])
        domain = dev["domain"]
        device_id = dev["config"]["device"]["identifiers"][0]
        async_fire_mqtt_message(
            hass, f"homeassistant/{domain}/{device_id}/config", data
        )
        await hass.async_block_till_done()

    for dev in devices:
        domain = dev["domain"]
        device_id = dev["config"]["device"]["identifiers"][0]
        device = device_registry.async_get_device(identifiers={("mqtt", device_id)})
        assert device is not None

        debug_info_data = debug_info.info_for_device(hass, device.id)
        if dev["domain"] != "device_automation":
            assert len(debug_info_data["entities"]) == 1
            assert len(debug_info_data["triggers"]) == 0
            discovery_data = debug_info_data["entities"][0]["discovery_data"]
            assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
            topic = dev["config"]["state_topic"]
            assert {"topic": topic, "messages": []} in debug_info_data["entities"][0][
                "subscriptions"
            ]
        else:
            assert len(debug_info_data["entities"]) == 0
            assert len(debug_info_data["triggers"]) == 1
            discovery_data = debug_info_data["triggers"][0]["discovery_data"]

        assert discovery_data["topic"] == f"homeassistant/{domain}/{device_id}/config"
        assert discovery_data["payload"] == dev["config"]


async def test_debug_info_multiple_entities_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test we get correct debug_info for a device with multiple entities and triggers."""
    await mqtt_mock_entry()
    config: list[_DebugInfo] = [
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

    for c in config:
        data = json.dumps(c["config"])
        domain = c["domain"]
        # Use topic as discovery_id
        discovery_id = c["config"].get("topic", c["config"].get("state_topic"))
        async_fire_mqtt_message(
            hass, f"homeassistant/{domain}/{discovery_id}/config", data
        )
        await hass.async_block_till_done()

    device_id = config[0]["config"]["device"]["identifiers"][0]
    device = device_registry.async_get_device(identifiers={("mqtt", device_id)})
    assert device is not None
    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 2
    assert len(debug_info_data["triggers"]) == 2

    for c in config:
        # Test we get debug info for each entity and trigger
        domain = c["domain"]
        # Use topic as discovery_id
        discovery_id = c["config"].get("topic", c["config"].get("state_topic"))

        if c["domain"] != "device_automation":
            discovery_data = [e["discovery_data"] for e in debug_info_data["entities"]]
            topic = c["config"]["state_topic"]
            assert {"topic": topic, "messages": []} in [
                t for e in debug_info_data["entities"] for t in e["subscriptions"]
            ]
        else:
            discovery_data = [e["discovery_data"] for e in debug_info_data["triggers"]]

        assert {
            "topic": f"homeassistant/{domain}/{discovery_id}/config",
            "payload": c["config"],
        } in discovery_data


async def test_debug_info_non_mqtt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_sensor_entities: dict[str, MockSensor],
) -> None:
    """Test we get empty debug_info for a device with non MQTT entities."""
    await mqtt_mock_entry()
    domain = "sensor"
    setup_test_component_platform(hass, domain, mock_sensor_entities.values())

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in SensorDeviceClass:
        entity_registry.async_get_or_create(
            domain,
            "test",
            mock_sensor_entities[device_class].unique_id,
            device_id=device_entry.id,
        )

    assert await async_setup_component(
        hass, mqtt.DOMAIN, {mqtt.DOMAIN: {domain: {"platform": "test"}}}
    )

    debug_info_data = debug_info.info_for_device(hass, device_entry.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 0


async def test_debug_info_wildcard(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test debug info."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(start_dt)
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


async def test_debug_info_same_topic(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test debug info."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "name": "test",
        "state_topic": "sensor/status",
        "availability_topic": "sensor/status",
        "unique_id": "veryunique",
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/status", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(start_dt)
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

    start_dt = datetime(2019, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(start_dt)
    async_fire_mqtt_message(hass, "sensor/status", "123", qos=0, retain=False)


async def test_debug_info_qos_retain(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test debug info."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(start_dt)
    # simulate the first message was replayed from the broker with retained flag
    async_fire_mqtt_message(hass, "sensor/abc", "123", qos=0, retain=True)
    # simulate an update message
    async_fire_mqtt_message(hass, "sensor/abc", "123", qos=0, retain=False)
    # simpulate someone else subscribed and retained messages were replayed
    async_fire_mqtt_message(hass, "sensor/abc", "123", qos=1, retain=True)
    # simulate an update message
    async_fire_mqtt_message(hass, "sensor/abc", "123", qos=1, retain=False)
    # simulate an update message
    async_fire_mqtt_message(hass, "sensor/abc", "123", qos=2, retain=False)

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    # The replayed retained payload was processed
    messages = debug_info_data["entities"][0]["subscriptions"][0]["messages"]
    assert {
        "payload": "123",
        "qos": 0,
        "retain": True,
        "time": start_dt,
        "topic": "sensor/abc",
    } in messages
    # The not retained update was processed normally
    assert {
        "payload": "123",
        "qos": 0,
        "retain": False,
        "time": start_dt,
        "topic": "sensor/abc",
    } in messages
    # Since the MQTT client has not lost the connection and has not resubscribed
    # The retained payload is not replayed and filtered out as it already
    # received a value and appears to be received on an existing subscription
    assert {
        "payload": "123",
        "qos": 1,
        "retain": True,
        "time": start_dt,
        "topic": "sensor/abc",
    } not in messages
    # The not retained update was processed normally
    assert {
        "payload": "123",
        "qos": 1,
        "retain": False,
        "time": start_dt,
        "topic": "sensor/abc",
    } in messages
    # The not retained update was processed normally
    assert {
        "payload": "123",
        "qos": 2,
        "retain": False,
        "time": start_dt,
        "topic": "sensor/abc",
    } in messages


async def test_subscribe_connection_status(
    hass: HomeAssistant,
    mock_debouncer: asyncio.Event,
    setup_with_birth_msg_client_mock: MqttMockPahoClient,
) -> None:
    """Test connextion status subscription."""

    mqtt_client_mock = setup_with_birth_msg_client_mock
    mqtt_connected_calls_callback: list[bool] = []
    mqtt_connected_calls_async: list[bool] = []

    @callback
    def async_mqtt_connected_callback(status: bool) -> None:
        """Update state on connection/disconnection to MQTT broker."""
        mqtt_connected_calls_callback.append(status)

    async def async_mqtt_connected_async(status: bool) -> None:
        """Update state on connection/disconnection to MQTT broker."""
        mqtt_connected_calls_async.append(status)

    # Check connection status
    assert mqtt.is_connected(hass) is True

    # Mock disconnect status
    mqtt_client_mock.on_disconnect(None, None, 0, MockMqttReasonCode())
    await hass.async_block_till_done()
    assert mqtt.is_connected(hass) is False

    unsub_callback = mqtt.async_subscribe_connection_status(
        hass, async_mqtt_connected_callback
    )
    unsub_async = mqtt.async_subscribe_connection_status(
        hass, async_mqtt_connected_async
    )
    await hass.async_block_till_done()

    # Mock connect status
    mock_debouncer.clear()
    mqtt_client_mock.on_connect(None, None, 0, MockMqttReasonCode())
    await mock_debouncer.wait()
    assert mqtt.is_connected(hass) is True

    # Mock disconnect status
    mqtt_client_mock.on_disconnect(None, None, 0, MockMqttReasonCode())
    await hass.async_block_till_done()
    assert mqtt.is_connected(hass) is False

    # Unsubscribe
    unsub_callback()
    unsub_async()

    # Mock connect status
    mock_debouncer.clear()
    mqtt_client_mock.on_connect(None, None, 0, MockMqttReasonCode())
    await mock_debouncer.wait()
    assert mqtt.is_connected(hass) is True

    # Check calls
    assert len(mqtt_connected_calls_callback) == 2
    assert mqtt_connected_calls_callback[0] is True
    assert mqtt_connected_calls_callback[1] is False

    assert len(mqtt_connected_calls_async) == 2
    assert mqtt_connected_calls_async[0] is True
    assert mqtt_connected_calls_async[1] is False


async def test_unload_config_entry(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading the MQTT entry."""
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={mqtt.CONF_BROKER: "test-broker"},
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, mqtt.DOMAIN, {})
    assert hass.services.has_service(mqtt.DOMAIN, "dump")
    assert hass.services.has_service(mqtt.DOMAIN, "publish")

    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED

    # Publish just before unloading to test await cleanup
    mqtt_client_mock.reset_mock()
    mqtt.publish(hass, "just_in_time", "published", qos=0, retain=False)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mqtt_config_entry.entry_id)
    new_mqtt_config_entry = mqtt_config_entry
    mqtt_client_mock.publish.assert_any_call("just_in_time", "published", 0, False)
    assert new_mqtt_config_entry.state is ConfigEntryState.NOT_LOADED
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.services.has_service(mqtt.DOMAIN, "dump")
    assert hass.services.has_service(mqtt.DOMAIN, "publish")
    assert "No ACK from MQTT server" not in caplog.text


async def test_publish_or_subscribe_without_valid_config_entry(
    hass: HomeAssistant, record_calls: MessageCallbackType
) -> None:
    """Test internal publish function with bad use cases."""
    assert await async_setup_component(hass, mqtt.DOMAIN, {})
    assert hass.services.has_service(mqtt.DOMAIN, "dump")
    assert hass.services.has_service(mqtt.DOMAIN, "publish")
    with pytest.raises(HomeAssistantError):
        await mqtt.async_publish(
            hass, "some-topic", "test-payload", qos=0, retain=False, encoding=None
        )
    with pytest.raises(HomeAssistantError):
        await mqtt.async_subscribe(hass, "some-topic", record_calls, qos=0)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": {
                "alarm_control_panel": [
                    {
                        "name": "test",
                        "state_topic": "home/alarm",
                        "command_topic": "home/alarm/set",
                    },
                ],
                "light": [{"name": "test", "command_topic": "test-topic_new"}],
            }
        }
    ],
)
async def test_disabling_and_enabling_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test disabling and enabling the config entry."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED
    # Late discovery of a mqtt entity
    config_tag = '{"topic": "0AFFD2/tag_scanned", "value_template": "{{ value_json.PN532.UID }}"}'
    config_alarm_control_panel = '{"name": "test_new", "state_topic": "home/alarm", "command_topic": "home/alarm/set"}'
    config_light = '{"name": "test_new", "command_topic": "test-topic_new"}'

    with patch(
        "homeassistant.components.mqtt.entity.mqtt_config_entry_enabled",
        return_value=False,
    ):
        # Discovery of mqtt tag
        async_fire_mqtt_message(hass, "homeassistant/tag/abc/config", config_tag)

        # Late discovery of mqtt entities
        async_fire_mqtt_message(
            hass,
            "homeassistant/alarm_control_panel/abc/config",
            config_alarm_control_panel,
        )
        async_fire_mqtt_message(hass, "homeassistant/light/abc/config", config_light)

    # Disable MQTT config entry
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert (
        "MQTT integration is disabled, skipping setup of discovered item MQTT tag"
        in caplog.text
    )
    assert (
        "MQTT integration is disabled, skipping setup of discovered item MQTT alarm_control_panel"
        in caplog.text
    )
    assert (
        "MQTT integration is disabled, skipping setup of discovered item MQTT light"
        in caplog.text
    )

    new_mqtt_config_entry = entry
    assert new_mqtt_config_entry.state is ConfigEntryState.NOT_LOADED

    # Enable the entry again
    await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    new_mqtt_config_entry = entry
    assert new_mqtt_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("light.test") is not None
    assert hass.states.get("alarm_control_panel.test") is not None


@pytest.mark.parametrize(
    ("hass_config", "unique"),
    [
        (
            {
                mqtt.DOMAIN: {
                    "light": [
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
                    ]
                }
            },
            False,
        ),
        (
            {
                mqtt.DOMAIN: {
                    "light": [
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
                    ]
                }
            },
            True,
        ),
    ],
)
async def test_setup_manual_items_with_unique_ids(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    unique: bool,
) -> None:
    """Test setup manual items is generating unique id's."""
    await mqtt_mock_entry()

    assert hass.states.get("light.test1") is not None
    assert (hass.states.get("light.test2") is not None) == unique
    assert bool("Platform mqtt does not generate unique IDs." in caplog.text) != unique

    # reload and assert again
    caplog.clear()
    await hass.services.async_call(
        "mqtt",
        SERVICE_RELOAD,
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.test1") is not None
    assert (hass.states.get("light.test2") is not None) == unique
    assert bool("Platform mqtt does not generate unique IDs." in caplog.text) != unique


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": {
                "sensor": [
                    {
                        "name": "test_manual",
                        "unique_id": "test_manual_unique_id123",
                        "state_topic": "test-topic_manual",
                    }
                ]
            }
        }
    ],
)
async def test_link_config_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test manual and dynamically setup entities are linked to the config entry."""
    # set up manual item
    await mqtt_mock_entry()

    # set up item through discovery
    config_discovery = {
        "name": "test_discovery",
        "unique_id": "test_discovery_unique456",
        "state_topic": "test-topic_discovery",
    }
    async_fire_mqtt_message(
        hass, "homeassistant/sensor/bla/config", json.dumps(config_discovery)
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_manual") is not None
    assert hass.states.get("sensor.test_discovery") is not None
    entity_names = ["test_manual", "test_discovery"]

    # Check if both entities were linked to the MQTT config entry
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    mqtt_platforms = async_get_platforms(hass, mqtt.DOMAIN)

    @callback
    def _check_entities() -> int:
        entities: list[Entity] = []
        for mqtt_platform in mqtt_platforms:
            assert mqtt_platform.config_entry is mqtt_config_entry
            entities += (entity for entity in mqtt_platform.entities.values())

        for entity in entities:
            assert entity.name in entity_names
        return len(entities)

    assert _check_entities() == 2

    # reload entry and assert again
    with patch("homeassistant.components.mqtt.async_client.AsyncMQTTClient"):
        await hass.config_entries.async_reload(mqtt_config_entry.entry_id)
        await hass.async_block_till_done()

    # manual set up item should remain
    assert _check_entities() == 1
    # set up item through discovery
    async_fire_mqtt_message(
        hass, "homeassistant/sensor/bla/config", json.dumps(config_discovery)
    )
    await hass.async_block_till_done()
    assert _check_entities() == 2

    # reload manual configured items and assert again
    await hass.services.async_call(
        "mqtt",
        SERVICE_RELOAD,
        {},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert _check_entities() == 2


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": {
                "sensor": [
                    {
                        "name": "test_manual1",
                        "unique_id": "test_manual_unique_id123",
                        "state_topic": "test-topic_manual1",
                    },
                    {
                        "name": "test_manual3",
                        "unique_id": "test_manual_unique_id789",
                        "state_topic": "test-topic_manual3",
                    },
                ]
            }
        }
    ],
)
async def test_reload_config_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test manual entities reloaded and set up correctly."""
    await mqtt_mock_entry()

    # set up item through discovery
    config_discovery = {
        "name": "test_discovery",
        "unique_id": "test_discovery_unique456",
        "state_topic": "test-topic_discovery",
    }
    async_fire_mqtt_message(
        hass, "homeassistant/sensor/bla/config", json.dumps(config_discovery)
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_discovery") is not None

    entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    @callback
    def _check_entities() -> int:
        entities: list[Entity] = []
        mqtt_platforms = async_get_platforms(hass, mqtt.DOMAIN)
        for mqtt_platform in mqtt_platforms:
            assert mqtt_platform.config_entry is entry
            entities += (entity for entity in mqtt_platform.entities.values())

        return len(entities)

    # assert on initial set up manual items

    async_fire_mqtt_message(hass, "test-topic_manual1", "manual1_intial")
    async_fire_mqtt_message(hass, "test-topic_manual3", "manual3_intial")

    assert (state := hass.states.get("sensor.test_manual1")) is not None
    assert state.attributes["friendly_name"] == "test_manual1"
    assert state.state == "manual1_intial"
    assert (state := hass.states.get("sensor.test_manual3")) is not None
    assert state.attributes["friendly_name"] == "test_manual3"
    assert state.state == "manual3_intial"
    assert _check_entities() == 3

    # Reload the entry with a new configuration.yaml
    # Mock configuration.yaml was updated
    # The first item was updated, a new item was added, an item was removed
    hass_config_new = {
        "mqtt": {
            "sensor": [
                {
                    "name": "test_manual1_updated",
                    "unique_id": "test_manual_unique_id123",
                    "state_topic": "test-topic_manual1_updated",
                },
                {
                    "name": "test_manual2_new",
                    "unique_id": "test_manual_unique_id456",
                    "state_topic": "test-topic_manual2",
                },
            ]
        }
    }
    with patch(
        "homeassistant.config.load_yaml_config_file", return_value=hass_config_new
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.test_manual1")) is not None
    assert state.attributes["friendly_name"] == "test_manual1_updated"
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get("sensor.test_manual2_new")) is not None
    assert state.attributes["friendly_name"] == "test_manual2_new"
    assert state.state is STATE_UNKNOWN
    # State of test_manual3 is still loaded but is unavailable
    assert (state := hass.states.get("sensor.test_manual3")) is not None
    assert state.state is STATE_UNAVAILABLE
    assert (state := hass.states.get("sensor.test_discovery")) is not None
    assert state.state is STATE_UNAVAILABLE
    # The entity is not loaded anymore
    assert _check_entities() == 2

    async_fire_mqtt_message(hass, "test-topic_manual1_updated", "manual1_update")
    async_fire_mqtt_message(hass, "test-topic_manual2", "manual2_update")
    async_fire_mqtt_message(hass, "test-topic_manual3", "manual3_update")

    assert (state := hass.states.get("sensor.test_manual1")) is not None
    assert state.state == "manual1_update"
    assert (state := hass.states.get("sensor.test_manual2_new")) is not None
    assert state.state == "manual2_update"
    assert (state := hass.states.get("sensor.test_manual3")) is not None
    assert state.state is STATE_UNAVAILABLE

    # Reload manual configured items and assert again
    with patch(
        "homeassistant.config.load_yaml_config_file", return_value=hass_config_new
    ):
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.test_manual1")) is not None
    assert state.attributes["friendly_name"] == "test_manual1_updated"
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get("sensor.test_manual2_new")) is not None
    assert state.attributes["friendly_name"] == "test_manual2_new"
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get("sensor.test_manual3")) is not None
    assert state.state == STATE_UNAVAILABLE
    assert _check_entities() == 2

    async_fire_mqtt_message(
        hass, "test-topic_manual1_updated", "manual1_update_after_reload"
    )
    async_fire_mqtt_message(hass, "test-topic_manual2", "manual2_update_after_reload")
    async_fire_mqtt_message(hass, "test-topic_manual3", "manual3_update_after_reload")

    assert (state := hass.states.get("sensor.test_manual1")) is not None
    assert state.state == "manual1_update_after_reload"
    assert (state := hass.states.get("sensor.test_manual2_new")) is not None
    assert state.state == "manual2_update_after_reload"
    assert (state := hass.states.get("sensor.test_manual3")) is not None
    assert state.state is STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": [
                {
                    "sensor": {
                        "name": "test",
                        "state_topic": "test-topic",
                    }
                },
            ]
        }
    ],
)
async def test_reload_with_invalid_config(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test reloading yaml config fails."""
    await mqtt_mock_entry()
    assert hass.states.get("sensor.test") is not None

    # Reload with an invalid config and assert again
    invalid_config = {"mqtt": "some_invalid_config"}
    with patch(
        "homeassistant.config.load_yaml_config_file", return_value=invalid_config
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "mqtt",
                SERVICE_RELOAD,
                {},
                blocking=True,
            )
        await hass.async_block_till_done()

    # Test nothing changed as loading the config failed
    assert hass.states.get("sensor.test") is not None


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": [
                {
                    "sensor": {
                        "name": "test",
                        "state_topic": "test-topic",
                    }
                },
            ]
        }
    ],
)
async def test_reload_with_empty_config(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test reloading yaml config fails."""
    await mqtt_mock_entry()
    assert hass.states.get("sensor.test") is not None

    # Reload with an empty config and assert again
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.test") is None


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": [
                {
                    "sensor": {
                        "name": "test",
                        "state_topic": "test-topic",
                    }
                },
            ]
        }
    ],
)
async def test_reload_with_new_platform_config(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test reloading yaml with new platform config."""
    await mqtt_mock_entry()
    assert hass.states.get("sensor.test") is not None
    assert hass.states.get("binary_sensor.test") is None

    new_config = {
        "mqtt": [
            {
                "sensor": {
                    "name": "test",
                    "state_topic": "test-topic1",
                },
                "binary_sensor": {
                    "name": "test",
                    "state_topic": "test-topic2",
                },
            },
        ]
    }

    # Reload with an new platform config and assert again
    with patch("homeassistant.config.load_yaml_config_file", return_value=new_config):
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.test") is not None
    assert hass.states.get("binary_sensor.test") is not None


async def test_multi_platform_discovery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test setting up multiple platforms simultaneous."""
    await mqtt_mock_entry()
    entity_configs = {
        "alarm_control_panel": {
            "name": "test",
            "state_topic": "alarm/state",
            "command_topic": "alarm/command",
        },
        "button": {"name": "test", "command_topic": "test-topic"},
        "camera": {"name": "test", "topic": "test_topic"},
        "cover": {"name": "test", "state_topic": "test-topic"},
        "device_tracker": {
            "name": "test",
            "state_topic": "test-topic",
        },
        "fan": {
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
        },
        "sensor": {"name": "test", "state_topic": "test-topic"},
        "switch": {"name": "test", "command_topic": "test-topic"},
        "select": {
            "name": "test",
            "command_topic": "test-topic",
            "options": ["milk", "beer"],
        },
    }
    non_entity_configs = {
        "tag": {
            "device": {"identifiers": ["tag_0AFFD2"]},
            "topic": "foobar/tag_scanned",
        },
        "device_automation": {
            "automation_type": "trigger",
            "device": {"identifiers": ["device_automation_0AFFD2"]},
            "payload": "short_press",
            "topic": "foobar/triggers/button1",
            "type": "button_short_press",
            "subtype": "button_1",
        },
    }
    for platform, config in entity_configs.items():
        for set_number in range(2):
            set_config = deepcopy(config)
            set_config["name"] = f"test_{set_number}"
            topic = f"homeassistant/{platform}/bla_{set_number}/config"
            async_fire_mqtt_message(hass, topic, json.dumps(set_config))
    for platform, config in non_entity_configs.items():
        topic = f"homeassistant/{platform}/bla/config"
        async_fire_mqtt_message(hass, topic, json.dumps(config))
    await hass.async_block_till_done()
    for set_number in range(2):
        for platform in entity_configs:
            entity_id = f"{platform}.test_{set_number}"
            state = hass.states.get(entity_id)
            assert state is not None
    for platform in non_entity_configs:
        assert (
            device_registry.async_get_device(
                identifiers={("mqtt", f"{platform}_0AFFD2")}
            )
            is not None
        )


@pytest.mark.parametrize(
    "attr",
    [
        "EntitySubscription",
        "MqttCommandTemplate",
        "MqttValueTemplate",
        "PayloadSentinel",
        "PublishPayloadType",
        "ReceiveMessage",
        "async_prepare_subscribe_topics",
        "async_publish",
        "async_subscribe",
        "async_subscribe_topics",
        "async_unsubscribe_topics",
        "async_wait_for_mqtt_client",
        "publish",
        "subscribe",
        "valid_publish_topic",
        "valid_qos_schema",
        "valid_subscribe_topic",
    ],
)
async def test_mqtt_integration_level_imports(attr: str) -> None:
    """Test mqtt integration level public published imports are available."""
    assert hasattr(mqtt, attr)
