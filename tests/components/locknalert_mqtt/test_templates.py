"""Tests for locknalert_mqtt templates module."""

import logging
from unittest.mock import MagicMock, patch

import jinja2
import pytest

from homeassistant.components.locknalert_mqtt.models import PayloadSentinel
from homeassistant.components.locknalert_mqtt.templates import (
    MqttCommandTemplate,
    MqttCommandTemplateException,
    MqttValueTemplate,
    MqttValueTemplateException,
    convert_outgoing_mqtt_payload,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template


# --- convert_outgoing_mqtt_payload ---


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (None, None),
        (42, 42),
        (3.14, 3.14),
        (b"\x00\x01", b"\x00\x01"),
        ("plain string", "plain string"),
        ("b'\\x00\\x01'", b"\x00\x01"),
        ('b"hello"', b"hello"),
        ("b'invalid escape \\q'", "b'invalid escape \\q'"),
        ("b'not bytes result'", "b'not bytes result'"),
    ],
    ids=[
        "none_unchanged",
        "int_unchanged",
        "float_unchanged",
        "bytes_unchanged",
        "plain_string_unchanged",
        "bytes_literal_single_quote",
        "bytes_literal_double_quote",
        "invalid_escape_unchanged",
        "non_bytes_literal_unchanged",
    ],
)
def test_convert_outgoing_mqtt_payload(
    payload: object, expected: object
) -> None:
    """Test convert_outgoing_mqtt_payload with various input types."""
    assert convert_outgoing_mqtt_payload(payload) == expected


def test_convert_outgoing_mqtt_payload_bytes_literal_becomes_non_bytes() -> None:
    """Eval result that is not bytes is returned as the original string."""
    payload = "b'123'"
    result = convert_outgoing_mqtt_payload(payload)
    assert result == b"123"


# --- MqttCommandTemplateException ---


def test_mqtt_command_template_exception_with_entity_id() -> None:
    """Exception message includes entity id when provided."""
    cause = ValueError("bad value")
    exc = MqttCommandTemplateException(
        base_exception=cause,
        command_template="{{ value }}",
        value="payload",
        entity_id="alarm_control_panel.test",
    )
    msg = str(exc)
    assert "alarm_control_panel.test" in msg
    assert "{{ value }}" in msg
    assert "payload" in msg
    assert exc.translation_key == "command_template_error"


def test_mqtt_command_template_exception_without_entity_id() -> None:
    """Exception message omits entity id when not provided."""
    cause = TemplateError(jinja2.TemplateError("broken"))
    exc = MqttCommandTemplateException(
        base_exception=cause,
        command_template="{{ value | unknown_filter }}",
        value=None,
    )
    msg = str(exc)
    assert "for entity" not in msg
    assert "{{ value | unknown_filter }}" in msg


# --- MqttCommandTemplate ---


def test_mqtt_command_template_none_returns_value() -> None:
    """When no template, async_render passes the value through unchanged."""
    cmd = MqttCommandTemplate(None)
    assert cmd.async_render("some_value") == "some_value"
    assert cmd.async_render(None) is None
    assert cmd.async_render(42) == 42


def test_mqtt_command_template_renders_value(hass: HomeAssistant) -> None:
    """Template receives value and produces rendered output."""
    tpl = template.Template("{{ value | upper }}", hass)
    cmd = MqttCommandTemplate(tpl)
    assert cmd.async_render("hello") == "HELLO"


def test_mqtt_command_template_renders_with_variables(hass: HomeAssistant) -> None:
    """Extra variables are accessible inside the template."""
    tpl = template.Template("{{ value }}_{{ extra }}", hass)
    cmd = MqttCommandTemplate(tpl)
    assert cmd.async_render("v", variables={"extra": "x"}) == "v_x"


def test_mqtt_command_template_raises_on_error(hass: HomeAssistant) -> None:
    """TemplateError during render is wrapped in MqttCommandTemplateException."""
    tpl = template.Template("{{ value | unknown_filter_xyz }}", hass)
    cmd = MqttCommandTemplate(tpl)
    with pytest.raises(MqttCommandTemplateException):
        cmd.async_render("hello")


def test_mqtt_command_template_with_entity(hass: HomeAssistant) -> None:
    """When an entity is set, entity_id and name are injected as template vars."""
    tpl = template.Template("{{ entity_id }}_{{ name }}", hass)
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.front_door"
    entity.name = "Front Door"
    entity.hass = hass
    cmd = MqttCommandTemplate(tpl, entity=entity)
    result = cmd.async_render("ignored")
    assert "alarm_control_panel.front_door" in result
    assert "Front Door" in result


def test_mqtt_command_template_with_entity_sets_template_state(
    hass: HomeAssistant,
) -> None:
    """_template_state is created lazily on first render when hass is available."""
    tpl = template.Template("{{ value }}", hass)
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.test"
    entity.name = "Test"
    entity.hass = hass
    cmd = MqttCommandTemplate(tpl, entity=entity)
    assert cmd._template_state is None
    cmd.async_render("x")
    assert cmd._template_state is not None


def test_mqtt_command_template_error_includes_entity_id(hass: HomeAssistant) -> None:
    """MqttCommandTemplateException includes the entity id from the entity."""
    tpl = template.Template("{{ value | unknown_filter_xyz }}", hass)
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.test"
    entity.name = "Test"
    entity.hass = hass
    cmd = MqttCommandTemplate(tpl, entity=entity)
    with pytest.raises(MqttCommandTemplateException) as exc_info:
        cmd.async_render("payload")
    assert "alarm_control_panel.test" in str(exc_info.value)


# --- MqttValueTemplateException ---


def test_mqtt_value_template_exception_with_entity_id() -> None:
    """MqttValueTemplateException message includes entity_id and template."""
    cause = ValueError("bad")
    exc = MqttValueTemplateException(
        base_exception=cause,
        value_template="{{ value }}",
        default=PayloadSentinel.NONE,
        payload="raw",
        entity_id="sensor.test",
    )
    msg = str(exc)
    assert "sensor.test" in msg
    assert "{{ value }}" in msg
    assert "raw" in msg


def test_mqtt_value_template_exception_without_entity_id() -> None:
    """MqttValueTemplateException omits entity clause when entity_id is None."""
    cause = TypeError("oops")
    exc = MqttValueTemplateException(
        base_exception=cause,
        value_template="{{ x }}",
        default="fallback",
        payload="input",
    )
    msg = str(exc)
    assert "for entity" not in msg
    assert "fallback" in msg


def test_mqtt_value_template_exception_with_sentinel_none_omits_default() -> None:
    """When default is PayloadSentinel.NONE, default is excluded from message."""
    cause = ValueError("x")
    exc = MqttValueTemplateException(
        base_exception=cause,
        value_template="{{ x }}",
        default=PayloadSentinel.NONE,
        payload="p",
    )
    assert "default value" not in str(exc)


def test_mqtt_value_template_exception_with_real_default_includes_it() -> None:
    """When a real default is provided, it appears in the message."""
    cause = ValueError("x")
    exc = MqttValueTemplateException(
        base_exception=cause,
        value_template="{{ x }}",
        default="my_default",
        payload="p",
    )
    assert "my_default" in str(exc)


# --- MqttValueTemplate ---


def test_mqtt_value_template_none_returns_payload() -> None:
    """When no template, async_render_with_possible_json_value returns payload unchanged."""
    vt = MqttValueTemplate(None)
    assert vt.async_render_with_possible_json_value("raw_payload") == "raw_payload"
    assert vt.async_render_with_possible_json_value(b"bytes") == b"bytes"


def test_mqtt_value_template_renders_payload(hass: HomeAssistant) -> None:
    """Template renders the incoming payload."""
    tpl = template.Template("{{ value | upper }}", hass)
    vt = MqttValueTemplate(tpl)
    assert vt.async_render_with_possible_json_value("hello") == "HELLO"


def test_mqtt_value_template_renders_with_variables(hass: HomeAssistant) -> None:
    """Extra variables are accessible in value templates."""
    tpl = template.Template("{{ value }}_{{ extra }}", hass)
    vt = MqttValueTemplate(tpl)
    result = vt.async_render_with_possible_json_value("v", variables={"extra": "x"})
    assert result == "v_x"


def test_mqtt_value_template_with_config_attributes(hass: HomeAssistant) -> None:
    """Config attributes are injected as static template variables."""
    tpl = template.Template("{{ multiplier }}", hass)
    vt = MqttValueTemplate(tpl, config_attributes={"multiplier": 3})
    assert vt.async_render_with_possible_json_value("ignored") == "3"


def test_mqtt_value_template_with_entity(hass: HomeAssistant) -> None:
    """When entity is set, entity_id and name are available as template vars."""
    tpl = template.Template("{{ entity_id }}", hass)
    entity = MagicMock()
    entity.entity_id = "sensor.temp"
    entity.name = "Temp"
    tpl.hass = hass
    vt = MqttValueTemplate(tpl, entity=entity)
    result = vt.async_render_with_possible_json_value("any")
    assert result == "sensor.temp"


def test_mqtt_value_template_raises_with_sentinel_none(hass: HomeAssistant) -> None:
    """When default is PayloadSentinel.NONE a template error raises."""
    tpl = template.Template("{{ value | unknown_filter_xyz }}", hass)
    vt = MqttValueTemplate(tpl)
    with pytest.raises(MqttValueTemplateException):
        vt.async_render_with_possible_json_value(
            "payload", default=PayloadSentinel.NONE
        )


def test_mqtt_value_template_raises_with_real_default(hass: HomeAssistant) -> None:
    """When a default is provided, a template error still raises MqttValueTemplateException."""
    tpl = template.Template("{{ value | unknown_filter_xyz }}", hass)
    vt = MqttValueTemplate(tpl)
    with pytest.raises(MqttValueTemplateException):
        vt.async_render_with_possible_json_value("payload", default="fallback")


def test_mqtt_value_template_default_used_on_missing_value(
    hass: HomeAssistant,
) -> None:
    """When value is missing in JSON payload, HA template uses the provided default."""
    tpl = template.Template("{{ value_json.missing_key }}", hass)
    vt = MqttValueTemplate(tpl)
    result = vt.async_render_with_possible_json_value(
        '{"other": 1}', default="DEFAULT"
    )
    assert result == "DEFAULT"


def test_mqtt_value_template_entity_sets_template_state_lazily(
    hass: HomeAssistant,
) -> None:
    """_template_state is created lazily on first render when hass is available."""
    tpl = template.Template("{{ value }}", hass)
    entity = MagicMock()
    entity.entity_id = "sensor.test"
    entity.name = "Test"
    tpl.hass = hass
    vt = MqttValueTemplate(tpl, entity=entity)
    assert vt._template_state is None
    vt.async_render_with_possible_json_value("x")
    assert vt._template_state is not None


def test_mqtt_value_template_error_includes_entity_id(hass: HomeAssistant) -> None:
    """MqttValueTemplateException includes entity_id from the entity."""
    tpl = template.Template("{{ value | unknown_filter_xyz }}", hass)
    entity = MagicMock()
    entity.entity_id = "sensor.test"
    entity.name = "Test"
    tpl.hass = hass
    vt = MqttValueTemplate(tpl, entity=entity)
    with pytest.raises(MqttValueTemplateException) as exc_info:
        vt.async_render_with_possible_json_value("payload", default=PayloadSentinel.NONE)
    assert "sensor.test" in str(exc_info.value)
