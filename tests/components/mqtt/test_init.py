"""The tests for the MQTT component."""
import asyncio
from collections.abc import Generator
from datetime import datetime, timedelta
from functools import partial
import json
import ssl
from typing import Any, TypedDict
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest
import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import debug_info
from homeassistant.components.mqtt.client import EnsureJobAfterCooldown
from homeassistant.components.mqtt.mixins import MQTT_ENTITY_DEVICE_INFO_SCHEMA
from homeassistant.components.mqtt.models import MessageCallbackType, ReceiveMessage
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfTemperature,
)
import homeassistant.core as ha
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er, template
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .test_common import help_all_subscribe_calls

from tests.common import (
    MockConfigEntry,
    MockEntity,
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_restore_cache,
)
from tests.testing_config.custom_components.test.sensor import (  # type: ignore[attr-defined]
    DEVICE_CLASSES,
)
from tests.typing import (
    MqttMockHAClient,
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


class RecordCallsPartial(partial[Any]):
    """Wrapper class for partial."""

    __name__ = "RecordCallPartialTest"


@pytest.fixture(autouse=True)
def sensor_platforms_only() -> Generator[None, None, None]:
    """Only setup the sensor platforms to speed up tests."""
    with patch(
        "homeassistant.components.mqtt.PLATFORMS",
        [Platform.SENSOR, Platform.BINARY_SENSOR],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_storage(hass_storage: dict[str, Any]) -> None:
    """Autouse hass_storage for the TestCase tests."""


@pytest.fixture
def calls() -> list[ReceiveMessage]:
    """Fixture to hold recorded calls."""
    return []


@pytest.fixture
def record_calls(calls: list[ReceiveMessage]) -> MessageCallbackType:
    """Fixture to record calls."""

    @callback
    def record_calls(msg: ReceiveMessage) -> None:
        """Record calls."""
        calls.append(msg)

    return record_calls


def help_assert_message(
    msg: ReceiveMessage,
    topic: str | None = None,
    payload: str | None = None,
    qos: int | None = None,
    retain: bool | None = None,
) -> bool:
    """Return True if all of the given attributes match with the message."""
    match: bool = True
    if topic is not None:
        match &= msg.topic == topic
    if payload is not None:
        match &= msg.payload == payload
    if qos is not None:
        match &= msg.qos == qos
    if retain is not None:
        match &= msg.retain == retain
    return match


async def test_mqtt_connects_on_home_assistant_mqtt_setup(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test if client is connected after mqtt init on bootstrap."""
    await mqtt_mock_entry()
    assert mqtt_client_mock.connect.call_count == 1


async def test_mqtt_disconnects_on_home_assistant_stop(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test if client stops on HA stop."""
    await mqtt_mock_entry()
    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mqtt_client_mock.loop_stop.call_count == 1


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_mqtt_await_ack_at_disconnect(
    hass: HomeAssistant,
) -> None:
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


async def test_publish(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the publish function."""
    mqtt_mock = await mqtt_mock_entry()
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


async def test_convert_outgoing_payload(hass: HomeAssistant) -> None:
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


async def test_command_template_value(hass: HomeAssistant) -> None:
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


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.SELECT])
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: ConfigType,
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


async def test_value_template_value(hass: HomeAssistant) -> None:
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


async def test_value_template_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the rendering of MQTT value template fails."""

    # test rendering a value fails
    entity = MockEntity(entity_id="sensor.test")
    entity.hass = hass
    tpl = template.Template("{{ value_json.some_var * 2 }}")
    val_tpl = mqtt.MqttValueTemplate(tpl, hass=hass, entity=entity)
    with pytest.raises(TypeError):
        val_tpl.async_render_with_possible_json_value('{"some_var": null }')
    await hass.async_block_till_done()
    assert (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' "
        "rendering template for entity 'sensor.test', "
        "template: '{{ value_json.some_var * 2 }}'"
    ) in caplog.text
    caplog.clear()
    with pytest.raises(TypeError):
        val_tpl.async_render_with_possible_json_value(
            '{"some_var": null }', default=100
        )
    assert (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' "
        "rendering template for entity 'sensor.test', "
        "template: '{{ value_json.some_var * 2 }}', default value: 100 and payload: "
        '{"some_var": null }'
    ) in caplog.text


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


async def test_service_call_with_topic_and_topic_template_does_not_publish(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with topic/topic template.

    If both 'topic' and 'topic_template' are provided then fail.
    """
    mqtt_mock = await mqtt_mock_entry()
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with a problematic topic template."""
    mqtt_mock = await mqtt_mock_entry()
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with rendered topic template.

    If 'topic_template' is provided and 'topic' is not, then render it.
    """
    mqtt_mock = await mqtt_mock_entry()
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with rendered, invalid topic template.

    If a wildcard topic is rendered, then fail.
    """
    mqtt_mock = await mqtt_mock_entry()
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with unrendered template.

    If both 'payload' and 'payload_template' are provided then fail.
    """
    mqtt_mock = await mqtt_mock_entry()
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with rendered template.

    If 'payload_template' is provided and 'payload' is not, then render it.
    """
    mqtt_mock = await mqtt_mock_entry()
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


async def test_service_call_with_bad_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with a bad template does not publish."""
    mqtt_mock = await mqtt_mock_entry()
    await hass.services.async_call(
        mqtt.DOMAIN,
        mqtt.SERVICE_PUBLISH,
        {mqtt.ATTR_TOPIC: "test/topic", mqtt.ATTR_PAYLOAD_TEMPLATE: "{{ 1 | bad }}"},
        blocking=True,
    )
    assert not mqtt_mock.async_publish.called


async def test_service_call_with_payload_doesnt_render_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the service call with unrendered template.

    If both 'payload' and 'payload_template' are provided then fail.
    """
    mqtt_mock = await mqtt_mock_entry()
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
async def test_handle_logging_on_writing_the_entity_state(
    hass: HomeAssistant,
    mock_hass_config: None,
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
        assert "Exception raised when updating state of" in caplog.text


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


async def test_all_subscriptions_run_when_decode_fails(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test all other subscriptions still run when decode fails for one."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic", record_calls, encoding="ascii")
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", UnitOfTemperature.CELSIUS)

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of a topic."""
    await mqtt_mock_entry()
    unsub = await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload"

    unsub()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1

    # Cannot unsubscribe twice
    with pytest.raises(HomeAssistantError):
        unsub()


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.UNSUBSCRIBE_COOLDOWN", 0.2)
async def test_subscribe_and_resubscribe(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test resubscribing within the debounce time."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test-topic", record_calls)
    # This unsub will be un-done with the following subscribe
    # unsubscribe should not be called at the broker
    unsub()
    await asyncio.sleep(0.1)
    unsub = await mqtt.async_subscribe(hass, "test-topic", record_calls)
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload"
    # assert unsubscribe was not called
    mqtt_client_mock.unsubscribe.assert_not_called()

    unsub()

    await asyncio.sleep(0.2)
    await hass.async_block_till_done()
    mqtt_client_mock.unsubscribe.assert_called_once_with(["test-topic"])


async def test_subscribe_topic_non_async(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of a topic using the non-async function."""
    await mqtt_mock_entry()
    unsub = await hass.async_add_executor_job(
        mqtt.subscribe, hass, "test-topic", record_calls
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload"

    await hass.async_add_executor_job(unsub)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_subscribe_bad_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of a topic."""
    await mqtt_mock_entry()
    with pytest.raises(HomeAssistantError):
        await mqtt.async_subscribe(hass, 55, record_calls)  # type: ignore[arg-type]


async def test_subscribe_topic_not_match(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test if subscribed topic is not a match."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic", record_calls)

    async_fire_mqtt_message(hass, "another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic/+/on", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "test-topic/bier/on"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_no_subtree_match(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic/+/on", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_root_topic_no_subtree_match(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic-123", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_subtree_wildcard_subtree_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic/bier/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "test-topic/bier/on"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_subtree_wildcard_root_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_subtree_wildcard_no_match(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_and_wildcard_root_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "hi/test-topic"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_and_wildcard_subtree_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/test-topic/here-iam", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "hi/test-topic/here-iam"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_level_wildcard_and_wildcard_level_no_match(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/here-iam/test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_level_wildcard_and_wildcard_no_match(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "+/test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "hi/another-test-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscribe_topic_sys_root(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of $ root topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "$test-topic/subtree/on", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/subtree/on", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "$test-topic/subtree/on"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_sys_root_and_wildcard_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of $ root and wildcard topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "$test-topic/#", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/some-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "$test-topic/some-topic"
    assert calls[0].payload == "test-payload"


async def test_subscribe_topic_sys_root_and_wildcard_subtree_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription of $ root and wildcard subtree topics."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "$test-topic/subtree/#", record_calls)

    async_fire_mqtt_message(hass, "$test-topic/subtree/some-topic", "test-payload")

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == "$test-topic/subtree/some-topic"
    assert calls[0].payload == "test-payload"


async def test_subscribe_special_characters(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    calls: list[ReceiveMessage],
    record_calls: MessageCallbackType,
) -> None:
    """Test the subscription to topics with special characters."""
    await mqtt_mock_entry()
    topic = "/test-topic/$(.)[^]{-}"
    payload = "p4y.l[]a|> ?"

    await mqtt.async_subscribe(hass, topic, record_calls)

    async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].topic == topic
    assert calls[0].payload == payload


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
async def test_subscribe_same_topic(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test subscribing to same topic twice and simulate retained messages.

    When subscribing to the same topic again, SUBSCRIBE must be sent to the broker again
    for it to resend any retained messages.
    """
    mqtt_mock = await mqtt_mock_entry()

    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a: list[ReceiveMessage] = []
    calls_b: list[ReceiveMessage] = []

    def _callback_a(msg: ReceiveMessage) -> None:
        calls_a.append(msg)

    def _callback_b(msg: ReceiveMessage) -> None:
        calls_b.append(msg)

    await mqtt.async_subscribe(hass, "test/state", _callback_a, qos=0)
    # Simulate a non retained message after the first subscription
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=False)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls_a) == 1
    mqtt_client_mock.subscribe.assert_called()
    calls_a = []
    mqtt_client_mock.reset_mock()

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    await mqtt.async_subscribe(hass, "test/state", _callback_b, qos=1)
    # Simulate an other non retained message after the second subscription
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=False)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    # Both subscriptions should receive updates
    assert len(calls_a) == 1
    assert len(calls_b) == 1
    mqtt_client_mock.subscribe.assert_called()


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
async def test_replaying_payload_same_topic(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test replaying retained messages.

    When subscribing to the same topic again, SUBSCRIBE must be sent to the broker again
    for it to resend any retained messages for new subscriptions.
    Retained messages must only be replayed for new subscriptions, except
    when the MQTT client is reconnecting.
    """
    mqtt_mock = await mqtt_mock_entry()

    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a: list[ReceiveMessage] = []
    calls_b: list[ReceiveMessage] = []

    def _callback_a(msg: ReceiveMessage) -> None:
        calls_a.append(msg)

    def _callback_b(msg: ReceiveMessage) -> None:
        calls_b.append(msg)

    await mqtt.async_subscribe(hass, "test/state", _callback_a)
    async_fire_mqtt_message(
        hass, "test/state", "online", qos=0, retain=True
    )  # Simulate a (retained) message played back
    await hass.async_block_till_done()
    assert len(calls_a) == 1
    mqtt_client_mock.subscribe.assert_called()
    calls_a = []
    mqtt_client_mock.reset_mock()

    await mqtt.async_subscribe(hass, "test/state", _callback_b)

    # Simulate edge case where non retained message was received
    # after subscription at HA but before the debouncer delay was passed.
    # The message without retain flag directly after a subscription should
    # be processed by both subscriptions.
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=False)

    # Simulate a (retained) message played back on new subscriptions
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=True)

    # Make sure the debouncer delay was passed
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    # The current subscription only received the message without retain flag
    assert len(calls_a) == 1
    assert help_assert_message(calls_a[0], "test/state", "online", qos=0, retain=False)
    # The retained message playback should only be processed by the new subscription.
    # The existing subscription already got the latest update, hence the existing
    # subscription should not receive the replayed (retained) message.
    # Messages without retain flag are received on both subscriptions.
    assert len(calls_b) == 2
    assert help_assert_message(calls_b[0], "test/state", "online", qos=0, retain=False)
    assert help_assert_message(calls_b[1], "test/state", "online", qos=0, retain=True)
    mqtt_client_mock.subscribe.assert_called()

    calls_a = []
    calls_b = []
    mqtt_client_mock.reset_mock()

    # Simulate new message played back on new subscriptions
    # After connecting the retain flag will not be set, even if the
    # payload published was retained, we cannot see that
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=False)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    assert len(calls_a) == 1
    assert help_assert_message(calls_a[0], "test/state", "online", qos=0, retain=False)
    assert len(calls_b) == 1
    assert help_assert_message(calls_b[0], "test/state", "online", qos=0, retain=False)

    # Now simulate the broker was disconnected shortly
    calls_a = []
    calls_b = []
    mqtt_client_mock.reset_mock()
    mqtt_client_mock.on_disconnect(None, None, 0)
    mqtt_client_mock.on_connect(None, None, None, 0)
    await hass.async_block_till_done()
    mqtt_client_mock.subscribe.assert_called()
    # Simulate a (retained) message played back after reconnecting
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=True)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    # Both subscriptions now should replay the retained message
    assert len(calls_a) == 1
    assert help_assert_message(calls_a[0], "test/state", "online", qos=0, retain=True)
    assert len(calls_b) == 1
    assert help_assert_message(calls_b[0], "test/state", "online", qos=0, retain=True)


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
async def test_replaying_payload_after_resubscribing(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test replaying and filtering retained messages after resubscribing.

    When subscribing to the same topic again, SUBSCRIBE must be sent to the broker again
    for it to resend any retained messages for new subscriptions.
    Retained messages must only be replayed for new subscriptions, except
    when the MQTT client is reconnection.
    """
    mqtt_mock = await mqtt_mock_entry()

    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a: list[ReceiveMessage] = []

    def _callback_a(msg: ReceiveMessage) -> None:
        calls_a.append(msg)

    unsub = await mqtt.async_subscribe(hass, "test/state", _callback_a)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    mqtt_client_mock.subscribe.assert_called()

    # Simulate a (retained) message played back
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=True)
    await hass.async_block_till_done()
    assert help_assert_message(calls_a[0], "test/state", "online", qos=0, retain=True)
    calls_a.clear()

    # Test we get updates
    async_fire_mqtt_message(hass, "test/state", "offline", qos=0, retain=False)
    await hass.async_block_till_done()
    assert help_assert_message(calls_a[0], "test/state", "offline", qos=0, retain=False)
    calls_a.clear()

    # Test we filter new retained updates
    async_fire_mqtt_message(hass, "test/state", "offline", qos=0, retain=True)
    await hass.async_block_till_done()
    assert len(calls_a) == 0

    # Unsubscribe an resubscribe again
    unsub()
    unsub = await mqtt.async_subscribe(hass, "test/state", _callback_a)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    mqtt_client_mock.subscribe.assert_called()

    # Simulate we can receive a (retained) played back message again
    async_fire_mqtt_message(hass, "test/state", "online", qos=0, retain=True)
    await hass.async_block_till_done()
    assert help_assert_message(calls_a[0], "test/state", "online", qos=0, retain=True)


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
async def test_replaying_payload_wildcard_topic(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test replaying retained messages.

    When we have multiple subscriptions to the same wildcard topic,
    SUBSCRIBE must be sent to the broker again
    for it to resend any retained messages for new subscriptions.
    Retained messages should only be replayed for new subscriptions, except
    when the MQTT client is reconnection.
    """
    mqtt_mock = await mqtt_mock_entry()

    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a: list[ReceiveMessage] = []
    calls_b: list[ReceiveMessage] = []

    def _callback_a(msg: ReceiveMessage) -> None:
        calls_a.append(msg)

    def _callback_b(msg: ReceiveMessage) -> None:
        calls_b.append(msg)

    await mqtt.async_subscribe(hass, "test/#", _callback_a)
    # Simulate (retained) messages being played back on new subscriptions
    async_fire_mqtt_message(hass, "test/state1", "new_value_1", qos=0, retain=True)
    async_fire_mqtt_message(hass, "test/state2", "new_value_2", qos=0, retain=True)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    assert len(calls_a) == 2
    mqtt_client_mock.subscribe.assert_called()
    calls_a = []
    mqtt_client_mock.reset_mock()

    # resubscribe to the wild card topic again
    await mqtt.async_subscribe(hass, "test/#", _callback_b)
    # Simulate (retained) messages being played back on new subscriptions
    async_fire_mqtt_message(hass, "test/state1", "initial_value_1", qos=0, retain=True)
    async_fire_mqtt_message(hass, "test/state2", "initial_value_2", qos=0, retain=True)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    # The retained messages playback should only be processed for the new subscriptions
    assert len(calls_a) == 0
    assert len(calls_b) == 2
    mqtt_client_mock.subscribe.assert_called()

    calls_a = []
    calls_b = []
    mqtt_client_mock.reset_mock()

    # Simulate new messages being received
    async_fire_mqtt_message(hass, "test/state1", "update_value_1", qos=0, retain=False)
    async_fire_mqtt_message(hass, "test/state2", "update_value_2", qos=0, retain=False)
    await hass.async_block_till_done()
    assert len(calls_a) == 2
    assert len(calls_b) == 2

    # Now simulate the broker was disconnected shortly
    calls_a = []
    calls_b = []
    mqtt_client_mock.reset_mock()
    mqtt_client_mock.on_disconnect(None, None, 0)
    mqtt_client_mock.on_connect(None, None, None, 0)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    mqtt_client_mock.subscribe.assert_called()
    # Simulate the (retained) messages are played back after reconnecting
    # for all subscriptions
    async_fire_mqtt_message(hass, "test/state1", "update_value_1", qos=0, retain=True)
    async_fire_mqtt_message(hass, "test/state2", "update_value_2", qos=0, retain=True)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    # Both subscriptions should replay
    assert len(calls_a) == 2
    assert len(calls_b) == 2


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
async def test_not_calling_unsubscribe_with_active_subscribers(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test not calling unsubscribe() when other subscribers are active."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test/state", record_calls, 2)
    await mqtt.async_subscribe(hass, "test/state", record_calls, 1)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.called

    unsub()
    await hass.async_block_till_done()
    assert not mqtt_client_mock.unsubscribe.called


async def test_not_calling_subscribe_when_unsubscribed_within_cooldown(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test not calling subscribe() when it is unsubscribed.

    Make sure subscriptions are cleared if unsubscribed before
    the subscribe cool down period has ended.
    """
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test/state", record_calls)
    unsub()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    assert not mqtt_client_mock.subscribe.called


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
async def test_unsubscribe_race(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test not calling unsubscribe() when other subscribers are active."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    calls_a: list[ReceiveMessage] = []
    calls_b: list[ReceiveMessage] = []

    def _callback_a(msg: ReceiveMessage) -> None:
        calls_a.append(msg)

    def _callback_b(msg: ReceiveMessage) -> None:
        calls_b.append(msg)

    mqtt_client_mock.reset_mock()
    unsub = await mqtt.async_subscribe(hass, "test/state", _callback_a)
    unsub()
    await mqtt.async_subscribe(hass, "test/state", _callback_b)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test/state", "online")
    await hass.async_block_till_done()
    assert not calls_a
    assert calls_b

    # We allow either calls [subscribe, unsubscribe, subscribe], [subscribe, subscribe] or
    # when both subscriptions were combined [subscribe]
    expected_calls_1 = [
        call.subscribe([("test/state", 0)]),
        call.unsubscribe("test/state"),
        call.subscribe([("test/state", 0)]),
    ]
    expected_calls_2 = [
        call.subscribe([("test/state", 0)]),
        call.subscribe([("test/state", 0)]),
    ]
    expected_calls_3 = [
        call.subscribe([("test/state", 0)]),
    ]
    assert mqtt_client_mock.mock_calls in (
        expected_calls_1,
        expected_calls_2,
        expected_calls_3,
    )


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
async def test_restore_subscriptions_on_reconnect(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test subscriptions are restored on reconnect."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    await mqtt.async_subscribe(hass, "test/state", record_calls)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.call_count == 1

    mqtt_client_mock.on_disconnect(None, None, 0)
    mqtt_client_mock.on_connect(None, None, None, 0)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mqtt_client_mock.subscribe.call_count == 2


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 1.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 1.0)
async def test_restore_all_active_subscriptions_on_reconnect(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test active subscriptions are restored correctly on reconnect."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    unsub = await mqtt.async_subscribe(hass, "test/state", record_calls, qos=2)
    await mqtt.async_subscribe(hass, "test/state", record_calls, qos=1)
    await mqtt.async_subscribe(hass, "test/state", record_calls, qos=0)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()

    # the subscribtion with the highest QoS should survive
    expected = [
        call([("test/state", 2)]),
    ]
    assert mqtt_client_mock.subscribe.mock_calls == expected

    unsub()
    await hass.async_block_till_done()
    assert mqtt_client_mock.unsubscribe.call_count == 0

    mqtt_client_mock.on_disconnect(None, None, 0)
    await hass.async_block_till_done()
    mqtt_client_mock.on_connect(None, None, None, 0)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()

    expected.append(call([("test/state", 1)]))
    assert mqtt_client_mock.subscribe.mock_calls == expected

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=3))  # cooldown
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 1.0)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 1.0)
async def test_subscribed_at_highest_qos(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test the highest qos as assigned when subscribing to the same topic."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    await mqtt.async_subscribe(hass, "test/state", record_calls, qos=0)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))  # cooldown
    await hass.async_block_till_done()
    assert ("test/state", 0) in help_all_subscribe_calls(mqtt_client_mock)
    mqtt_client_mock.reset_mock()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))  # cooldown
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    await mqtt.async_subscribe(hass, "test/state", record_calls, qos=1)
    await mqtt.async_subscribe(hass, "test/state", record_calls, qos=2)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))  # cooldown
    await hass.async_block_till_done()
    # the subscribtion with the highest QoS should survive
    assert help_all_subscribe_calls(mqtt_client_mock) == [("test/state", 2)]


async def test_reload_entry_with_restored_subscriptions(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    record_calls: MessageCallbackType,
    calls: list[ReceiveMessage],
) -> None:
    """Test reloading the config entry with with subscriptions restored."""
    # Setup the MQTT entry
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)
    mqtt_client_mock.connect.return_value = 0
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        await entry.async_setup(hass)

    await mqtt.async_subscribe(hass, "test-topic", record_calls)
    await mqtt.async_subscribe(hass, "wild/+/card", record_calls)

    async_fire_mqtt_message(hass, "test-topic", "test-payload")
    async_fire_mqtt_message(hass, "wild/any/card", "wild-card-payload")

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload"
    assert calls[1].topic == "wild/any/card"
    assert calls[1].payload == "wild-card-payload"
    calls.clear()

    # Reload the entry
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED
        await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test-topic", "test-payload2")
    async_fire_mqtt_message(hass, "wild/any/card", "wild-card-payload2")

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload2"
    assert calls[1].topic == "wild/any/card"
    assert calls[1].payload == "wild-card-payload2"
    calls.clear()

    # Reload the entry again
    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED
        await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test-topic", "test-payload3")
    async_fire_mqtt_message(hass, "wild/any/card", "wild-card-payload3")

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].topic == "test-topic"
    assert calls[0].payload == "test-payload3"
    assert calls[1].topic == "wild/any/card"
    assert calls[1].payload == "wild-card-payload3"


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 2)
@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 2)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 2)
async def test_canceling_debouncer_on_shutdown(
    hass: HomeAssistant,
    record_calls: MessageCallbackType,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test canceling the debouncer when HA shuts down."""

    mqtt_mock = await mqtt_mock_entry()

    # Fake that the client is connected
    mqtt_mock().connected = True

    await mqtt.async_subscribe(hass, "test/state1", record_calls)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.2))
    await hass.async_block_till_done()

    await mqtt.async_subscribe(hass, "test/state2", record_calls)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.2))
    await hass.async_block_till_done()

    await mqtt.async_subscribe(hass, "test/state3", record_calls)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.2))
    await hass.async_block_till_done()

    await mqtt.async_subscribe(hass, "test/state4", record_calls)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.2))
    await hass.async_block_till_done()

    await mqtt.async_subscribe(hass, "test/state5", record_calls)

    mqtt_client_mock.subscribe.assert_not_called()

    # Stop HA so the scheduled task will be canceled
    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
    # mock disconnect status
    mqtt_client_mock.on_disconnect(None, None, 0)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    mqtt_client_mock.subscribe.assert_not_called()


async def test_canceling_debouncer_normal(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test canceling the debouncer before completion."""

    async def _async_myjob() -> None:
        await asyncio.sleep(1.0)

    debouncer = EnsureJobAfterCooldown(0.0, _async_myjob)
    debouncer.async_schedule()
    await asyncio.sleep(0.01)
    assert debouncer._task is not None
    await debouncer.async_cleanup()
    assert debouncer._task is None


async def test_canceling_debouncer_throws(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test canceling the debouncer when HA shuts down."""

    async def _async_myjob() -> None:
        await asyncio.sleep(1.0)

    debouncer = EnsureJobAfterCooldown(0.0, _async_myjob)
    debouncer.async_schedule()
    await asyncio.sleep(0.01)
    assert debouncer._task is not None
    # let debouncer._task fail by mocking it
    with patch.object(debouncer, "_task") as task:
        task.cancel = MagicMock(return_value=True)
        await debouncer.async_cleanup()
        assert "Error cleaning up task" in caplog.text
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()


async def test_initial_setup_logs_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
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
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test for setup failure if connection to broker is missing."""
    await mqtt_mock_entry()
    # test with rc = 3 -> broker unavailable
    mqtt_client_mock.on_connect(mqtt_client_mock, None, None, 3)
    await hass.async_block_till_done()
    assert (
        "Unable to connect to the MQTT broker: Connection Refused: broker unavailable."
        in caplog.text
    )


@patch("homeassistant.components.mqtt.client.TIMEOUT_ACK", 0.3)
async def test_handle_mqtt_on_callback(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test receiving an ACK callback before waiting for it."""
    await mqtt_mock_entry()
    # Simulate an ACK for mid == 1, this will call mqtt_mock._mqtt_handle_mid(mid)
    mqtt_client_mock.on_publish(mqtt_client_mock, None, 1)
    await hass.async_block_till_done()
    # Make sure the ACK has been received
    await hass.async_block_till_done()
    # Now call publish without call back, this will call _wait_for_mid(msg_info.mid)
    await mqtt.async_publish(hass, "no_callback/test-topic", "test-payload")
    # Since the mid event was already set, we should not see any timeout warning in the log
    await hass.async_block_till_done()
    assert "No ACK from MQTT server" not in caplog.text


async def test_publish_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
async def test_subscribe_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
    record_calls: MessageCallbackType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test publish error."""
    await mqtt_mock_entry()
    mqtt_client_mock.on_connect(mqtt_client_mock, None, None, 0)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_client_mock.reset_mock()
    # simulate client is not connected error before subscribing
    mqtt_client_mock.subscribe.side_effect = lambda *args: (4, None)
    await mqtt.async_subscribe(hass, "some-topic", record_calls)
    while mqtt_client_mock.subscribe.call_count == 0:
        await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert (
        "Error talking to MQTT: The client is not currently connected." in caplog.text
    )


async def test_handle_message_callback(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test for handling an incoming message callback."""
    callbacks = []

    @callback
    def _callback(args) -> None:
        callbacks.append(args)

    mock_mqtt = await mqtt_mock_entry()
    msg = ReceiveMessage("some-topic", b"test-payload", 1, False)
    mqtt_client_mock.on_connect(mqtt_client_mock, None, None, 0)
    await mqtt.async_subscribe(hass, "some-topic", _callback)
    mqtt_client_mock.on_message(mock_mqtt, None, msg)

    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(callbacks) == 1
    assert callbacks[0].topic == "some-topic"
    assert callbacks[0].qos == 1
    assert callbacks[0].payload == "test-payload"


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
@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_manual_mqtt_with_platform_key(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test set up a manual MQTT item with a platform key."""
    with pytest.raises(AssertionError):
        await mqtt_mock_entry()
    assert (
        "Invalid config for [mqtt]: [platform] is an invalid option for [mqtt]"
        in caplog.text
    )


@pytest.mark.parametrize("hass_config", [{mqtt.DOMAIN: {"light": {"name": "test"}}}])
@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_manual_mqtt_with_invalid_config(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test set up a manual MQTT item with an invalid config."""
    with pytest.raises(AssertionError):
        await mqtt_mock_entry()
    assert (
        "Invalid config for [mqtt]: required key not provided @ data['mqtt'][0]['light'][0]['command_topic']. "
        "Got None. (See ?, line ?)" in caplog.text
    )


@patch("homeassistant.components.mqtt.PLATFORMS", [])
@pytest.mark.parametrize(
    ("mqtt_config_entry_data", "protocol"),
    [
        (
            {
                mqtt.CONF_BROKER: "mock-broker",
                mqtt.CONF_PROTOCOL: "3.1",
            },
            3,
        ),
        (
            {
                mqtt.CONF_BROKER: "mock-broker",
                mqtt.CONF_PROTOCOL: "3.1.1",
            },
            4,
        ),
        (
            {
                mqtt.CONF_BROKER: "mock-broker",
                mqtt.CONF_PROTOCOL: "5",
            },
            5,
        ),
    ],
)
async def test_setup_mqtt_client_protocol(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    protocol: int,
) -> None:
    """Test MQTT client protocol setup."""
    with patch("paho.mqtt.client.Client") as mock_client:
        await mqtt_mock_entry()

    # check if protocol setup was correctly
    assert mock_client.call_args[1]["protocol"] == protocol


@patch("homeassistant.components.mqtt.client.TIMEOUT_ACK", 0.2)
@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_handle_mqtt_timeout_on_callback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test publish without receiving an ACK callback."""
    mid = 0

    class FakeInfo:
        """Returns a simulated client publish response."""

        mid = 100
        rc = 0

    with patch("paho.mqtt.client.Client") as mock_client:

        def _mock_ack(topic: str, qos: int = 0) -> tuple[int, int]:
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


async def test_setup_raises_config_entry_not_ready_if_no_connect_broker(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = MagicMock(side_effect=OSError("Connection error"))
        assert await mqtt.async_setup_entry(hass, entry)
        await hass.async_block_till_done()
        assert "Failed to connect to MQTT server due to exception:" in caplog.text


@pytest.mark.parametrize(
    ("mqtt_config_entry_data", "insecure_param"),
    [
        ({"broker": "test-broker", "certificate": "auto"}, "not set"),
        (
            {"broker": "test-broker", "certificate": "auto", "tls_insecure": False},
            False,
        ),
        ({"broker": "test-broker", "certificate": "auto", "tls_insecure": True}, True),
    ],
)
@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_setup_uses_certificate_on_certificate_set_to_auto_and_insecure(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    insecure_param: bool | str,
) -> None:
    """Test setup uses bundled certs when certificate is set to auto and insecure."""
    calls = []
    insecure_check = {"insecure": "not set"}

    def mock_tls_set(
        certificate, certfile=None, keyfile=None, tls_version=None
    ) -> None:
        calls.append((certificate, certfile, keyfile, tls_version))

    def mock_tls_insecure_set(insecure_param) -> None:
        insecure_check["insecure"] = insecure_param

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().tls_set = mock_tls_set
        mock_client().tls_insecure_set = mock_tls_insecure_set
        await mqtt_mock_entry()
        await hass.async_block_till_done()

    assert calls

    import certifi

    expected_certificate = certifi.where()
    assert calls[0][0] == expected_certificate

    # test if insecure is set
    assert insecure_check["insecure"] == insecure_param


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_CERTIFICATE: "auto",
        }
    ],
)
async def test_tls_version(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test setup defaults for tls."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()
    assert (
        mqtt_client_mock.tls_set.mock_calls[0][2]["tls_version"]
        == ssl.PROTOCOL_TLS_CLIENT
    )


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
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test sending birth message."""
    await mqtt_mock_entry()
    birth = asyncio.Event()

    async def wait_birth(msg: ReceiveMessage) -> None:
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
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test sending birth message."""
    await mqtt_mock_entry()
    birth = asyncio.Event()

    async def wait_birth(msg: ReceiveMessage) -> None:
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
async def test_no_birth_message(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test disabling birth message."""
    await mqtt_mock_entry()
    with patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.1):
        mqtt_client_mock.on_connect(None, None, 0, 0)
        await hass.async_block_till_done()
        await asyncio.sleep(0.2)
        mqtt_client_mock.publish.assert_not_called()

    async def callback(msg: ReceiveMessage) -> None:
        """Handle birth message."""

    # Assert the subscribe debouncer subscribes after
    # about SUBSCRIBE_COOLDOWN (0.1) sec
    # but sooner than INITIAL_SUBSCRIBE_COOLDOWN (1.0)

    mqtt_client_mock.reset_mock()
    await mqtt.async_subscribe(hass, "homeassistant/some-topic", callback)
    await hass.async_block_till_done()
    await asyncio.sleep(0.2)
    mqtt_client_mock.subscribe.assert_called()


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
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test sending birth message does not happen until Home Assistant starts."""
    mqtt_mock = await mqtt_mock_entry()

    hass.state = CoreState.starting
    birth = asyncio.Event()

    await hass.async_block_till_done()

    entry = MockConfigEntry(domain=mqtt.DOMAIN, data=mqtt_config_entry_data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mqtt_component_mock = MagicMock(
        return_value=hass.data["mqtt"].client,
        wraps=hass.data["mqtt"].client,
    )
    mqtt_component_mock._mqttc = mqtt_client_mock

    hass.data["mqtt"].client = mqtt_component_mock
    mqtt_mock = hass.data["mqtt"].client
    mqtt_mock.reset_mock()

    async def wait_birth(msg: ReceiveMessage) -> None:
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
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test will message."""
    await mqtt_mock_entry()

    mqtt_client_mock.will_set.assert_called_with(
        topic="death", payload="death", qos=0, retain=False
    )


async def test_default_will_message(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test will message."""
    await mqtt_mock_entry()

    mqtt_client_mock.will_set.assert_called_with(
        topic="homeassistant/status", payload="offline", qos=0, retain=False
    )


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_WILL_MESSAGE: {}}],
)
async def test_no_will_message(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test will message."""
    await mqtt_mock_entry()

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
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test subscription to topic on connect."""
    await mqtt_mock_entry()

    await mqtt.async_subscribe(hass, "topic/test", record_calls)
    await mqtt.async_subscribe(hass, "home/sensor", record_calls, 2)
    await mqtt.async_subscribe(hass, "still/pending", record_calls)
    await mqtt.async_subscribe(hass, "still/pending", record_calls, 1)

    mqtt_client_mock.on_connect(None, None, 0, 0)

    await hass.async_block_till_done()

    assert mqtt_client_mock.disconnect.call_count == 0

    subscribe_calls = help_all_subscribe_calls(mqtt_client_mock)
    assert len(subscribe_calls) == 3
    assert ("topic/test", 0) in subscribe_calls
    assert ("home/sensor", 2) in subscribe_calls
    assert ("still/pending", 1) in subscribe_calls


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
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
async def test_mqtt_subscribes_in_single_call(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    record_calls: MessageCallbackType,
) -> None:
    """Test bundled client subscription to topic."""
    mqtt_mock = await mqtt_mock_entry()
    # Fake that the client is connected
    mqtt_mock().connected = True

    mqtt_client_mock.subscribe.reset_mock()
    await mqtt.async_subscribe(hass, "topic/test", record_calls)
    await mqtt.async_subscribe(hass, "home/sensor", record_calls)
    await hass.async_block_till_done()
    # Make sure the debouncer finishes
    await asyncio.sleep(0.2)

    assert mqtt_client_mock.subscribe.call_count == 1
    # Assert we have a single subscription call with both subscriptions
    assert mqtt_client_mock.subscribe.mock_calls[0][1][0] in [
        [("topic/test", 0), ("home/sensor", 0)],
        [("home/sensor", 0), ("topic/test", 0)],
    ]


async def test_default_entry_setting_are_applied(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if the MQTT component loads when config entry data not has all default settings."""
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    # Config entry data is incomplete but valid according the schema
    entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    entry.data = {"broker": "test-broker", "port": 1234}
    await mqtt_mock_entry()
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
    def bad_handler(*args) -> None:
        """Record calls."""
        raise ValueError("This is a bad message callback")

    await mqtt.async_subscribe(hass, "test-topic", bad_handler)
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

    # Subscribe with QoS 2
    await client.send_json(
        {"id": 9, "type": "mqtt/subscribe", "topic": "test-topic", "qos": 2}
    )
    response = await client.receive_json()
    assert response["success"]

    async_fire_mqtt_message(hass, "test-topic", "test1", 2)
    async_fire_mqtt_message(hass, "test-topic", "test2", 2)
    async_fire_mqtt_message(hass, "test-topic", b"\xDE\xAD\xBE\xEF", 2)

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
    config_sensor["platform"] = config_trigger["platform"] = mqtt.DOMAIN

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


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.CAMERA])
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
    config["platform"] = mqtt.DOMAIN

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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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

    registry = dr.async_get(hass)

    for dev in devices:
        data = json.dumps(dev["config"])
        domain = dev["domain"]
        id = dev["config"]["device"]["identifiers"][0]
        async_fire_mqtt_message(hass, f"homeassistant/{domain}/{id}/config", data)
        await hass.async_block_till_done()

    for dev in devices:
        domain = dev["domain"]
        id = dev["config"]["device"]["identifiers"][0]
        device = registry.async_get_device(identifiers={("mqtt", id)})
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

        assert discovery_data["topic"] == f"homeassistant/{domain}/{id}/config"
        assert discovery_data["payload"] == dev["config"]


async def test_debug_info_multiple_entities_triggers(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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

    registry = dr.async_get(hass)

    for c in config:
        data = json.dumps(c["config"])
        domain = c["domain"]
        # Use topic as discovery_id
        id = c["config"].get("topic", c["config"].get("state_topic"))
        async_fire_mqtt_message(hass, f"homeassistant/{domain}/{id}/config", data)
        await hass.async_block_till_done()

    device_id = config[0]["config"]["device"]["identifiers"][0]
    device = registry.async_get_device(identifiers={("mqtt", device_id)})
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
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test we get empty debug_info for a device with non MQTT entities."""
    await mqtt_mock_entry()
    domain = "sensor"
    platform = getattr(hass.components, f"test.{domain}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in DEVICE_CLASSES:
        entity_registry.async_get_or_create(
            domain,
            "test",
            platform.ENTITIES[device_class].unique_id,
            device_id=device_entry.id,
        )

    assert await async_setup_component(
        hass, mqtt.DOMAIN, {mqtt.DOMAIN: {domain: {"platform": "test"}}}
    )

    debug_info_data = debug_info.info_for_device(hass, device_entry.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 0


async def test_debug_info_wildcard(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test debug info."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
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


async def test_debug_info_filter_same(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test debug info removes messages with same timestamp."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
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


async def test_debug_info_same_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
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


async def test_debug_info_qos_retain(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test debug info."""
    await mqtt_mock_entry()
    config = {
        "device": {"identifiers": ["helloworld"]},
        "name": "test",
        "state_topic": "sensor/#",
        "unique_id": "veryunique",
    }

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
    assert {"topic": "sensor/#", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
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


async def test_publish_json_from_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the publishing of call to services."""
    mqtt_mock = await mqtt_mock_entry()

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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test connextion status subscription."""
    mqtt_mock = await mqtt_mock_entry()
    mqtt_connected_calls_callback: list[bool] = []
    mqtt_connected_calls_async: list[bool] = []

    @callback
    def async_mqtt_connected_callback(status: bool) -> None:
        """Update state on connection/disconnection to MQTT broker."""
        mqtt_connected_calls_callback.append(status)

    async def async_mqtt_connected_async(status: bool) -> None:
        """Update state on connection/disconnection to MQTT broker."""
        mqtt_connected_calls_async.append(status)

    mqtt_mock.connected = True

    unsub_callback = mqtt.async_subscribe_connection_status(
        hass, async_mqtt_connected_callback
    )
    unsub_async = mqtt.async_subscribe_connection_status(
        hass, async_mqtt_connected_async
    )
    await hass.async_block_till_done()

    # Mock connection status
    mqtt_client_mock.on_connect(None, None, 0, 0)
    await hass.async_block_till_done()
    assert mqtt.is_connected(hass) is True

    # Mock disconnect status
    mqtt_client_mock.on_disconnect(None, None, 0)
    await hass.async_block_till_done()

    # Unsubscribe
    unsub_callback()
    unsub_async()

    mqtt_client_mock.on_connect(None, None, 0, 0)
    await hass.async_block_till_done()

    # Check calls
    assert len(mqtt_connected_calls_callback) == 2
    assert mqtt_connected_calls_callback[0] is True
    assert mqtt_connected_calls_callback[1] is False

    assert len(mqtt_connected_calls_async) == 2
    assert mqtt_connected_calls_async[0] is True
    assert mqtt_connected_calls_async[1] is False


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
async def test_unload_config_entry(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_client_mock: MqttMockPahoClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading the MQTT entry."""
    assert hass.services.has_service(mqtt.DOMAIN, "dump")
    assert hass.services.has_service(mqtt.DOMAIN, "publish")

    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED

    # Publish just before unloading to test await cleanup
    mqtt_client_mock.reset_mock()
    mqtt.publish(hass, "just_in_time", "published", qos=0, retain=False)

    assert await hass.config_entries.async_unload(mqtt_config_entry.entry_id)
    new_mqtt_config_entry = mqtt_config_entry
    mqtt_client_mock.publish.assert_any_call("just_in_time", "published", 0, False)
    assert new_mqtt_config_entry.state is ConfigEntryState.NOT_LOADED
    await hass.async_block_till_done()
    assert not hass.services.has_service(mqtt.DOMAIN, "dump")
    assert not hass.services.has_service(mqtt.DOMAIN, "publish")
    assert "No ACK from MQTT server" not in caplog.text


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_publish_or_subscribe_without_valid_config_entry(
    hass: HomeAssistant, record_calls: MessageCallbackType
) -> None:
    """Test internal publish function with bas use cases."""
    with pytest.raises(HomeAssistantError):
        await mqtt.async_publish(
            hass, "some-topic", "test-payload", qos=0, retain=False, encoding=None
        )
    with pytest.raises(HomeAssistantError):
        await mqtt.async_subscribe(hass, "some-topic", record_calls, qos=0)


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": {
                "light": [
                    {"name": "test_new_modern", "command_topic": "test-topic_new"}
                ]
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
    # Late discovery of a light
    config = '{"name": "abc", "command_topic": "test-topic"}'
    async_fire_mqtt_message(hass, "homeassistant/light/abc/config", config)

    # Disable MQTT config entry
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()
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

    assert hass.states.get("light.test_new_modern") is not None


@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT])
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
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
    with patch("paho.mqtt.client.Client"):
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
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
