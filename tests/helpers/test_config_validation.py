"""Test config validators."""

from collections import OrderedDict
from datetime import date, datetime, timedelta
import enum
from functools import partial
import logging
import os
from socket import _GLOBAL_DEFAULT_TIMEOUT
import threading
from typing import Any
from unittest.mock import ANY, Mock, patch
import uuid

import py
import pytest
import voluptuous as vol

import homeassistant
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    selector,
    template,
)


def test_boolean() -> None:
    """Test boolean validation."""
    schema = vol.Schema(cv.boolean)

    for value in (
        None,
        "T",
        "negative",
        "lock",
        "tr  ue",  # codespell:ignore ue
        [],
        [1, 2],
        {"one": "two"},
        test_boolean,
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("true", "On", "1", "YES", "   true  ", "enable", 1, 50, True, 0.1):
        assert schema(value)

    for value in ("false", "Off", "0", "NO", "disable", 0, False):
        assert not schema(value)


def test_latitude() -> None:
    """Test latitude validation."""
    schema = vol.Schema(cv.latitude)

    for value in ("invalid", None, -91, 91, "-91", "91", "123.01A"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("-89", 89, "12.34"):
        schema(value)


def test_longitude() -> None:
    """Test longitude validation."""
    schema = vol.Schema(cv.longitude)

    for value in ("invalid", None, -181, 181, "-181", "181", "123.01A"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("-179", 179, "12.34"):
        schema(value)


def test_port() -> None:
    """Test TCP/UDP network port."""
    schema = vol.Schema(cv.port)

    for value in ("invalid", None, -1, 0, 80000, "81000"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("1000", 21, 24574):
        schema(value)


def test_isfile() -> None:
    """Validate that the value is an existing file."""
    schema = vol.Schema(cv.isfile)

    fake_file = "this-file-does-not.exist"
    assert not os.path.isfile(fake_file)

    for value in ("invalid", None, -1, 0, 80000, fake_file):
        with pytest.raises(vol.Invalid):
            schema(value)

    # patching methods that allow us to fake a file existing
    # with write access
    with (
        patch("os.path.isfile", Mock(return_value=True)),
        patch("os.access", Mock(return_value=True)),
    ):
        schema("test.txt")


def test_url() -> None:
    """Test URL."""
    schema = vol.Schema(cv.url)

    for value in (
        "invalid",
        None,
        100,
        "htp://ha.io",
        "http//ha.io",
        "http://??,**",
        "https://??,**",
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        "http://localhost",
        "https://localhost/test/index.html",
        "http://home-assistant.io",
        "http://home-assistant.io/test/",
        "https://community.home-assistant.io/",
    ):
        assert schema(value)


def test_configuration_url() -> None:
    """Test URL."""
    schema = vol.Schema(cv.configuration_url)

    for value in (
        "invalid",
        None,
        100,
        "htp://ha.io",
        "http//ha.io",
        "http://??,**",
        "https://??,**",
        "homeassistant://??,**",
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        "http://localhost",
        "https://localhost/test/index.html",
        "http://home-assistant.io",
        "http://home-assistant.io/test/",
        "https://community.home-assistant.io/",
        "homeassistant://api",
        "homeassistant://api/hassio_ingress/XXXXXXX",
    ):
        assert schema(value)


def test_url_no_path() -> None:
    """Test URL."""
    schema = vol.Schema(cv.url_no_path)

    for value in (
        "https://localhost/test/index.html",
        "http://home-assistant.io/test/",
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        "http://localhost",
        "http://home-assistant.io",
        "https://community.home-assistant.io/",
    ):
        assert schema(value)


def test_platform_config() -> None:
    """Test platform config validation."""
    options = ({}, {"hello": "world"})
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.PLATFORM_SCHEMA(value)

    options = ({"platform": "mqtt"}, {"platform": "mqtt", "beer": "yes"})
    for value in options:
        cv.PLATFORM_SCHEMA_BASE(value)


def test_ensure_list() -> None:
    """Test ensure_list."""
    schema = vol.Schema(cv.ensure_list)
    assert schema(None) == []
    assert schema(1) == [1]
    assert schema([1]) == [1]
    assert schema("1") == ["1"]
    assert schema(["1"]) == ["1"]
    assert schema({"1": "2"}) == [{"1": "2"}]


def test_entity_id() -> None:
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_id)

    with pytest.raises(vol.MultipleInvalid):
        schema("invalid_entity")

    assert schema("sensor.LIGHT") == "sensor.light"


@pytest.mark.parametrize("validator", [cv.entity_ids, cv.entity_ids_or_uuids])
def test_entity_ids(validator) -> None:
    """Test entity ID validation."""
    schema = vol.Schema(validator)

    options = (
        "invalid_entity",
        "sensor.light,sensor_invalid",
        ["invalid_entity"],
        ["sensor.light", "sensor_invalid"],
        ["sensor.light,sensor_invalid"],
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ([], ["sensor.light"], "sensor.light")
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, light.kitchen ") == ["sensor.light", "light.kitchen"]


def test_entity_ids_or_uuids() -> None:
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_ids_or_uuids)

    valid_uuid = "a266a680b608c32770e6c45bfe6b8411"
    valid_uuid2 = "a266a680b608c32770e6c45bfe6b8412"
    invalid_uuid_capital_letters = "A266A680B608C32770E6C45bfE6B8412"
    options = (
        "invalid_uuid",
        invalid_uuid_capital_letters,
        f"{valid_uuid},invalid_uuid",
        ["invalid_uuid"],
        [valid_uuid, "invalid_uuid"],
        [f"{valid_uuid},invalid_uuid"],
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ([], [valid_uuid], valid_uuid)
    for value in options:
        schema(value)

    assert schema(f"{valid_uuid}, {valid_uuid2} ") == [valid_uuid, valid_uuid2]


def test_entity_domain() -> None:
    """Test entity domain validation."""
    schema = vol.Schema(cv.entity_domain("sensor"))

    for value in (
        "invalid_entity",
        "cover.demo",
        "cover.demo,sensor.another_entity",
        "",
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    assert schema("sensor.LIGHT") == "sensor.light"

    schema = vol.Schema(cv.entity_domain(("sensor", "binary_sensor")))

    for value in ("invalid_entity", "cover.demo"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    assert schema("sensor.LIGHT") == "sensor.light"
    assert schema("binary_sensor.LIGHT") == "binary_sensor.light"


def test_entities_domain() -> None:
    """Test entities domain validation."""
    schema = vol.Schema(cv.entities_domain("sensor"))

    options = (
        None,
        "",
        "invalid_entity",
        ["sensor.light", "cover.demo"],
        ["sensor.light", "sensor_invalid"],
    )

    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ("sensor.light", ["SENSOR.light"], ["sensor.light", "sensor.demo"])
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, sensor.demo ") == ["sensor.light", "sensor.demo"]
    assert schema(["sensor.light", "SENSOR.demo"]) == ["sensor.light", "sensor.demo"]


def test_ensure_list_csv() -> None:
    """Test ensure_list_csv."""
    schema = vol.Schema(cv.ensure_list_csv)

    options = (None, 12, [], ["string"], "string1,string2")
    for value in options:
        schema(value)

    assert schema("string1, string2 ") == ["string1", "string2"]


def test_event_schema() -> None:
    """Test event_schema validation."""
    options = (
        {},
        None,
        {"event_data": {}},
        {"event": "state_changed", "event_data": 1},
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.EVENT_SCHEMA(value)

    options = (
        {"event": "state_changed"},
        {"event": "state_changed", "event_data": {"hello": "world"}},
    )
    for value in options:
        cv.EVENT_SCHEMA(value)


def test_icon() -> None:
    """Test icon validation."""
    schema = vol.Schema(cv.icon)

    for value in (False, "work"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema("mdi:work")
    schema("custom:prefix")


def test_time_period() -> None:
    """Test time_period validation."""
    schema = vol.Schema(cv.time_period)

    options = (
        None,
        "",
        "hello:world",
        "12:",
        "12:34:56:78",
        {},
        {"wrong_key": -10},
        "12.5:30",
        "12:30.5",
        "12.5:30:30",
        "12:30.5:30",
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        ("8:20", timedelta(hours=8, minutes=20)),
        ("23:59", timedelta(hours=23, minutes=59)),
        ("-8:20", -1 * timedelta(hours=8, minutes=20)),
        ("-1:15", -1 * timedelta(hours=1, minutes=15)),
        ("-23:59:59", -1 * timedelta(hours=23, minutes=59, seconds=59)),
        ("-48:00", -1 * timedelta(days=2)),
        ({"minutes": 5}, timedelta(minutes=5)),
        (1, timedelta(seconds=1)),
        ("5", timedelta(seconds=5)),
        ("180", timedelta(seconds=180)),
        ("00:08:20.5", timedelta(minutes=8, seconds=20, milliseconds=500)),
        ("00:23:59.999", timedelta(minutes=23, seconds=59, milliseconds=999)),
        ("-00:08:20.5", -1 * timedelta(minutes=8, seconds=20, milliseconds=500)),
        (
            "-12:59:59.999",
            -1 * timedelta(hours=12, minutes=59, seconds=59, milliseconds=999),
        ),
        ({"milliseconds": 1.5}, timedelta(milliseconds=1, microseconds=500)),
        ({"seconds": "1.5"}, timedelta(seconds=1, milliseconds=500)),
        ({"minutes": "1.5"}, timedelta(minutes=1, seconds=30)),
        ({"hours": -1.5}, -1 * timedelta(hours=1, minutes=30)),
        ({"days": "-1.5"}, -1 * timedelta(days=1, hours=12)),
    )
    for value, result in options:
        assert schema(value) == result


def test_remove_falsy() -> None:
    """Test remove falsy."""
    assert cv.remove_falsy([0, None, 1, "1", {}, [], ""]) == [1, "1"]


def test_service() -> None:
    """Test service validation."""
    schema = vol.Schema(cv.service)

    with pytest.raises(vol.MultipleInvalid):
        schema("invalid_turn_on")

    schema("homeassistant.turn_on")


@pytest.mark.parametrize(
    "config",
    [
        {"service": "homeassistant.turn_on"},
        {"service": "homeassistant.turn_on", "entity_id": "light.kitchen"},
        {"service": "light.turn_on", "entity_id": "all"},
        {
            "service": "homeassistant.turn_on",
            "entity_id": ["light.kitchen", "light.ceiling"],
        },
        {
            "service": "light.turn_on",
            "entity_id": "all",
            "alias": "turn on kitchen lights",
        },
        {"service": "scene.turn_on", "metadata": {}},
        {"action": "homeassistant.turn_on"},
        {"action": "homeassistant.turn_on", "entity_id": "light.kitchen"},
        {"action": "light.turn_on", "entity_id": "all"},
        {
            "action": "homeassistant.turn_on",
            "entity_id": ["light.kitchen", "light.ceiling"],
        },
        {
            "action": "light.turn_on",
            "entity_id": "all",
            "alias": "turn on kitchen lights",
        },
        {"action": "scene.turn_on", "metadata": {}},
    ],
)
def test_service_schema(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test service_schema validation."""
    validated = cv.SERVICE_SCHEMA(config)

    # Ensure metadata is removed from the validated output
    assert "metadata" not in validated

    # Ensure service is migrated to action
    assert "service" not in validated
    assert "action" in validated
    assert validated["action"] == config.get("service", config["action"])


@pytest.mark.parametrize(
    "config",
    [
        {},
        None,
        {"data": {"entity_id": "light.kitchen"}},
        {
            "service": "homeassistant.turn_on",
            "service_template": "homeassistant.turn_on",
        },
        {"service": "homeassistant.turn_on", "data": None},
        {
            "service": "homeassistant.turn_on",
            "data_template": {"brightness": "{{ no_end"},
        },
        {
            "service": "homeassistant.turn_on",
            "action": "homeassistant.turn_on",
        },
        {
            "action": "homeassistant.turn_on",
            "service_template": "homeassistant.turn_on",
        },
        {"action": "homeassistant.turn_on", "data": None},
        {
            "action": "homeassistant.turn_on",
            "data_template": {"brightness": "{{ no_end"},
        },
    ],
)
def test_invalid_service_schema(
    hass: HomeAssistant, config: dict[str, Any] | None
) -> None:
    """Test service_schema validation fails."""
    with pytest.raises(vol.MultipleInvalid):
        cv.SERVICE_SCHEMA(config)


def test_entity_service_schema() -> None:
    """Test make_entity_service_schema validation."""
    schema = cv.make_entity_service_schema(
        {vol.Required("required"): cv.positive_int, vol.Optional("optional"): cv.string}
    )

    options = (
        {},
        None,
        {"entity_id": "light.kitchen"},
        {"optional": "value", "entity_id": "light.kitchen"},
        {"required": 1},
        {"required": 2, "area_id": "kitchen", "foo": "bar"},
        {"required": "str", "area_id": "kitchen"},
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.SERVICE_SCHEMA(value)

    options = (
        {"required": 1, "entity_id": "light.kitchen"},
        {"required": 2, "optional": "value", "device_id": "a_device"},
        {"required": 3, "area_id": "kitchen"},
    )
    for value in options:
        schema(value)

    options = (
        {
            "required": 1,
            "entity_id": "light.kitchen",
            "metadata": {"some": "frontend_stuff"},
        },
    )
    for value in options:
        validated = schema(value)
        assert "metadata" not in validated


def test_entity_service_schema_with_metadata() -> None:
    """Test make_entity_service_schema with overridden metadata key."""
    schema = cv.make_entity_service_schema({vol.Required("metadata"): cv.positive_int})

    options = ({"metadata": {"some": "frontend_stuff"}, "entity_id": "light.kitchen"},)
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.SERVICE_SCHEMA(value)

    options = ({"metadata": 1, "entity_id": "light.kitchen"},)
    for value in options:
        validated = schema(value)
        assert "metadata" in validated


def test_slug() -> None:
    """Test slug validation."""
    schema = vol.Schema(cv.slug)

    for value in (None, "hello world"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (12345, "hello"):
        schema(value)


def test_string(hass: HomeAssistant) -> None:
    """Test string validation."""
    schema = vol.Schema(cv.string)

    with pytest.raises(vol.Invalid):
        schema(None)

    with pytest.raises(vol.Invalid):
        schema([])

    with pytest.raises(vol.Invalid):
        schema({})

    for value in (True, 1, "hello"):
        schema(value)

    # Test subclasses of str are returned
    class MyString(str):
        __slots__ = ()

    my_string = MyString("hello")
    assert schema(my_string) is my_string

    # Test template support
    for text, native in (
        ("[1, 2]", [1, 2]),
        ("{1, 2}", {1, 2}),
        ("(1, 2)", (1, 2)),
        ('{"hello": True}', {"hello": True}),
    ):
        tpl = template.Template(text, hass)
        result = tpl.async_render()
        assert isinstance(result, template.ResultWrapper)
        assert result == native
        assert schema(result) == text


def test_string_with_no_html() -> None:
    """Test string with no html validation."""
    schema = vol.Schema(cv.string_with_no_html)

    with pytest.raises(vol.Invalid):
        schema("This has HTML in it <a>Link</a>")

    with pytest.raises(vol.Invalid):
        schema("<b>Bold</b>")

    with pytest.raises(vol.Invalid):
        schema("HTML element names are <EM>case-insensitive</eM>.")

    for value in (
        True,
        3,
        "Hello",
        "**Hello**",
        "This has no HTML [Link](https://home-assistant.io)",
    ):
        schema(value)


def test_temperature_unit() -> None:
    """Test temperature unit validation."""
    schema = vol.Schema(cv.temperature_unit)

    with pytest.raises(vol.MultipleInvalid):
        schema("K")

    schema("C")
    schema("F")


def test_x10_address() -> None:
    """Test x10 addr validator."""
    schema = vol.Schema(cv.x10_address)
    with pytest.raises(vol.Invalid):
        schema("Q1")
    with pytest.raises(vol.Invalid):
        schema("q55")
    with pytest.raises(vol.Invalid):
        schema("garbage_addr")

    schema("a1")
    schema("C11")


def test_template(hass: HomeAssistant) -> None:
    """Test template validator."""
    schema = vol.Schema(cv.template)

    for value in (
        None,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
    ):
        with pytest.raises(vol.Invalid):
            schema(value)

    options = (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        # Function 'expand' added as an extension by Home Assistant
        "{{ expand('group.foo')|map(attribute='entity_id')|list }}",
        # Filter 'expand' added as an extension by Home Assistant
        "{{ ['group.foo']|expand|map(attribute='entity_id')|list }}",
        # Non existing function 'no_such_function' is not detected by Jinja2
        "{{ no_such_function('group.foo')|map(attribute='entity_id')|list }}",
    )
    for value in options:
        schema(value)


async def test_template_no_hass(hass: HomeAssistant) -> None:
    """Test template validator."""
    schema = vol.Schema(cv.template)

    for value in (
        None,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
        # Filter added as an extension by Home Assistant
        "{{ ['group.foo']|expand|map(attribute='entity_id')|list }}",
    ):
        with pytest.raises(vol.Invalid):
            await hass.async_add_executor_job(schema, value)

    options = (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        # Function 'expand' added as an extension by Home Assistant, no error
        # because non existing functions are not detected by Jinja2
        "{{ expand('group.foo')|map(attribute='entity_id')|list }}",
        # Non existing function 'no_such_function' is not detected by Jinja2
        "{{ no_such_function('group.foo')|map(attribute='entity_id')|list }}",
    )
    for value in options:
        await hass.async_add_executor_job(schema, value)


def test_dynamic_template(hass: HomeAssistant) -> None:
    """Test dynamic template validator."""
    schema = vol.Schema(cv.dynamic_template)

    for value in (
        None,
        1,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
        "just a string",
    ):
        with pytest.raises(vol.Invalid):
            schema(value)

    options = (
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        # Function 'expand' added as an extension by Home Assistant
        "{{ expand('group.foo')|map(attribute='entity_id')|list }}",
        # Filter 'expand' added as an extension by Home Assistant
        "{{ ['group.foo']|expand|map(attribute='entity_id')|list }}",
        # Non existing function 'no_such_function' is not detected by Jinja2
        "{{ no_such_function('group.foo')|map(attribute='entity_id')|list }}",
    )
    for value in options:
        schema(value)


async def test_dynamic_template_no_hass(hass: HomeAssistant) -> None:
    """Test dynamic template validator."""
    schema = vol.Schema(cv.dynamic_template)

    for value in (
        None,
        1,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
        "just a string",
        # Filter added as an extension by Home Assistant
        "{{ ['group.foo']|expand|map(attribute='entity_id')|list }}",
    ):
        with pytest.raises(vol.Invalid):
            await hass.async_add_executor_job(schema, value)

    options = (
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        # Function 'expand' added as an extension by Home Assistant, no error
        # because non existing functions are not detected by Jinja2
        "{{ expand('group.foo')|map(attribute='entity_id')|list }}",
        # Non existing function 'no_such_function' is not detected by Jinja2
        "{{ no_such_function('group.foo')|map(attribute='entity_id')|list }}",
    )
    for value in options:
        await hass.async_add_executor_job(schema, value)


def test_template_complex() -> None:
    """Test template_complex validator."""
    schema = vol.Schema(cv.template_complex)

    for value in ("{{ partial_print }", "{% if True %}Hello"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        {"test": 1, "test2": "{{ beer }}"},
        ["{{ beer }}", 1],
    )
    for value in options:
        schema(value)

    # ensure the validator didn't mutate the input
    assert options == (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        {"test": 1, "test2": "{{ beer }}"},
        ["{{ beer }}", 1],
    )

    # Ensure we don't mutate non-string types that cannot be templates.
    for value in (1, True, None):
        assert schema(value) == value


def test_time_zone() -> None:
    """Test time zone validation."""
    schema = vol.Schema(cv.time_zone)

    with pytest.raises(vol.MultipleInvalid):
        schema("America/Do_Not_Exist")

    schema("America/Los_Angeles")
    schema("UTC")


def test_date() -> None:
    """Test date validation."""
    schema = vol.Schema(cv.date)

    for value in ("Not a date", "23:42", "2016-11-23T18:59:08"):
        with pytest.raises(vol.Invalid):
            schema(value)

    schema(datetime.now().date())
    schema("2016-11-23")


def test_time() -> None:
    """Test date validation."""
    schema = vol.Schema(cv.time)

    for value in ("Not a time", "2016-11-23", "2016-11-23T18:59:08"):
        with pytest.raises(vol.Invalid):
            schema(value)

    schema(datetime.now().time())
    schema("23:42:00")
    schema("23:42")


def test_datetime() -> None:
    """Test date time validation."""
    schema = vol.Schema(cv.datetime)
    for value in (date.today(), "Wrong DateTime"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema(datetime.now())
    schema("2016-11-23T18:59:08")


def test_multi_select() -> None:
    """Test multi select validation.

    Expected behavior:
        - Will not accept any input but a list
        - Will not accept selections outside of configured scope
    """
    schema = vol.Schema(cv.multi_select({"paulus": "Paulus", "robban": "Robban"}))

    with pytest.raises(vol.Invalid):
        schema("robban")
    with pytest.raises(vol.Invalid):
        schema(["paulus", "martinhj"])

    schema(["robban", "paulus"])


def test_multi_select_in_serializer() -> None:
    """Test multi_select with custom_serializer."""
    assert cv.custom_serializer(cv.multi_select({"paulus": "Paulus"})) == {
        "type": "multi_select",
        "options": {"paulus": "Paulus"},
    }


def test_boolean_in_serializer() -> None:
    """Test boolean with custom_serializer."""
    assert cv.custom_serializer(cv.boolean) == {
        "type": "boolean",
    }


def test_string_in_serializer() -> None:
    """Test string with custom_serializer."""
    assert cv.custom_serializer(cv.string) == {
        "type": "string",
    }


def test_selector_in_serializer() -> None:
    """Test selector with custom_serializer."""
    assert cv.custom_serializer(selector.selector({"text": {}})) == {
        "selector": {
            "text": {
                "multiline": False,
                "multiple": False,
            }
        }
    }


def test_positive_time_period_dict_in_serializer() -> None:
    """Test positive_time_period_dict with custom_serializer."""
    assert cv.custom_serializer(cv.positive_time_period_dict) == {
        "type": "positive_time_period_dict",
    }


@pytest.fixture
def schema():
    """Create a schema used for testing deprecation."""
    return vol.Schema({"venus": cv.boolean, "mars": cv.boolean, "jupiter": cv.boolean})


@pytest.fixture
def version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the version used for testing to 0.5.0."""
    monkeypatch.setattr(homeassistant.const, "__version__", "0.5.0")


def test_deprecated_with_no_optionals(caplog: pytest.LogCaptureFixture, schema) -> None:
    """Test deprecation behaves correctly when optional params are None.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema without changing any values
        - No warning or difference in output if key is not provided
    """
    deprecated_schema = vol.All(cv.deprecated("mars"), schema)

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert caplog.records[0].name in [
        __name__,
        "homeassistant.helpers.config_validation",
    ]
    assert (
        "The 'mars' option is deprecated, please remove it from your configuration"
    ) in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_or_removed_param_and_raise(
    caplog: pytest.LogCaptureFixture, schema
) -> None:
    """Test removed or deprecation options and fail the config validation by raising an exception.

    Expected behavior:
        - Outputs the appropriate deprecation or removed from support error if key is detected
    """
    removed_schema = vol.All(cv.deprecated("mars", raise_if_present=True), schema)

    test_data = {"mars": True}
    with pytest.raises(vol.Invalid) as excinfo:
        removed_schema(test_data)
    assert (
        "The 'mars' option is deprecated, please remove it from your configuration"
        in str(excinfo.value)
    )
    assert len(caplog.records) == 0

    test_data = {"venus": True}
    output = removed_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    deprecated_schema = vol.All(cv.removed("mars"), schema)

    test_data = {"mars": True}
    with pytest.raises(vol.Invalid) as excinfo:
        deprecated_schema(test_data)
    assert (
        "The 'mars' option has been removed, please remove it from your configuration"
        in str(excinfo.value)
    )
    assert len(caplog.records) == 0

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_replacement_key(
    caplog: pytest.LogCaptureFixture, schema
) -> None:
    """Test deprecation behaves correctly when only a replacement key is provided.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning or difference in output if neither key nor
            replacement_key are provided
    """
    deprecated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter"), schema
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text
    assert output == {"jupiter": True}

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"jupiter": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_default(caplog: pytest.LogCaptureFixture, schema) -> None:
    """Test deprecation behaves correctly with a default value.

    This is likely a scenario that would never occur.

    Expected behavior:
        - Behaves identically as when the default value was not present
    """
    deprecated_schema = vol.All(cv.deprecated("mars", default=False), schema)

    test_data = {"mars": True}
    with patch(
        "homeassistant.helpers.config_validation.get_integration_logger",
        return_value=logging.getLogger(__name__),
    ):
        output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert caplog.records[0].name == __name__
    assert (
        "The 'mars' option is deprecated, please remove it from your configuration"
    ) in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_replacement_key_and_default(
    caplog: pytest.LogCaptureFixture, schema
) -> None:
    """Test deprecation with a replacement key and default.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
    """
    deprecated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter", default=False), schema
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text
    assert output == {"jupiter": True}

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"jupiter": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert output == {"venus": True, "jupiter": False}

    deprecated_schema_with_default = vol.All(
        vol.Schema(
            {
                "venus": cv.boolean,
                vol.Optional("mars", default=False): cv.boolean,
                vol.Optional("jupiter", default=False): cv.boolean,
            }
        ),
        cv.deprecated("mars", replacement_key="jupiter", default=False),
    )

    test_data = {"mars": True}
    output = deprecated_schema_with_default(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text
    assert output == {"jupiter": True}


def test_deprecated_cant_find_module() -> None:
    """Test if the current module cannot be found."""
    # This used to raise.
    cv.deprecated(
        "mars",
        replacement_key="jupiter",
        default=False,
    )

    # This used to raise.
    cv.removed(
        "mars",
        default=False,
    )


def test_deprecated_or_removed_logger_with_config_attributes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if the logger outputs the correct message if the line and file attribute is available in config."""
    file: str = "configuration.yaml"
    line: int = 54

    # test as deprecated option
    replacement_key = "jupiter"
    option_status = "is deprecated"
    replacement = f"'mars' option near {file}:{line} {option_status}, please replace it with '{replacement_key}'"
    config = OrderedDict([("mars", "blah")])
    setattr(config, "__config_file__", file)
    setattr(config, "__line__", line)

    validated = cv.deprecated("mars", replacement_key=replacement_key, default=False)(
        config
    )
    assert "mars" not in validated  # Removed because a replacement_key is defined

    assert len(caplog.records) == 1
    assert replacement in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0

    # test as removed option
    option_status = "has been removed"
    replacement = f"'mars' option near {file}:{line} {option_status}, please remove it from your configuration"
    config = OrderedDict([("mars", "blah")])
    setattr(config, "__config_file__", file)
    setattr(config, "__line__", line)

    validated = cv.removed("mars", default=False, raise_if_present=False)(config)
    assert "mars" not in validated  # Removed because by cv.removed

    assert len(caplog.records) == 1
    assert replacement in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0


def test_deprecated_logger_with_one_config_attribute(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if the logger outputs the correct message if only one of line and file attribute is available in config."""
    file: str = "configuration.yaml"
    line: int = 54
    replacement = f"'mars' option near {file}:{line} is deprecated"
    config = OrderedDict([("mars", "blah")])
    setattr(config, "__config_file__", file)

    cv.deprecated("mars", replacement_key="jupiter", default=False)(config)

    assert len(caplog.records) == 1
    assert replacement not in caplog.text
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0

    config = OrderedDict([("mars", "blah")])
    setattr(config, "__line__", line)

    cv.deprecated("mars", replacement_key="jupiter", default=False)(config)

    assert len(caplog.records) == 1
    assert replacement not in caplog.text
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0


def test_deprecated_logger_without_config_attributes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if the logger outputs the correct message if the line and file attribute is not available in config."""
    file: str = "configuration.yaml"
    line: int = 54
    replacement = f"'mars' option near {file}:{line} is deprecated"
    config = OrderedDict([("mars", "blah")])

    cv.deprecated("mars", replacement_key="jupiter", default=False)(config)

    assert len(caplog.records) == 1
    assert replacement not in caplog.text
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0


def test_key_dependency() -> None:
    """Test key_dependency validator."""
    schema = vol.Schema(cv.key_dependency("beer", "soda"))

    options = {"beer": None}
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ({"beer": None, "soda": None}, {"soda": None}, {})
    for value in options:
        schema(value)


def test_has_at_most_one_key() -> None:
    """Test has_at_most_one_key validator."""
    schema = vol.Schema(cv.has_at_most_one_key("beer", "soda"))

    for value in (None, [], {"beer": None, "soda": None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({}, {"beer": None}, {"soda": None}, {vol.Optional("soda"): None}):
        schema(value)


def test_has_at_least_one_key() -> None:
    """Test has_at_least_one_key validator."""
    schema = vol.Schema(cv.has_at_least_one_key("beer", "soda"))

    for value in (None, [], {}, {"wine": None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({"beer": None}, {"soda": None}, {vol.Required("soda"): None}):
        schema(value)


def test_enum() -> None:
    """Test enum validator."""

    class TestEnum(enum.Enum):
        """Test enum."""

        value1 = "Value 1"
        value2 = "Value 2"

    schema = vol.Schema(cv.enum(TestEnum))

    with pytest.raises(vol.Invalid):
        schema("value3")


def test_socket_timeout() -> None:
    """Test socket timeout validator."""
    schema = vol.Schema(cv.socket_timeout)

    with pytest.raises(vol.Invalid):
        schema(0.0)

    with pytest.raises(vol.Invalid):
        schema(-1)

    assert schema(None) == _GLOBAL_DEFAULT_TIMEOUT

    assert schema(1) == 1.0


def test_matches_regex() -> None:
    """Test matches_regex validator."""
    schema = vol.Schema(cv.matches_regex(".*uiae.*"))

    with pytest.raises(vol.Invalid):
        schema(1.0)

    with pytest.raises(vol.Invalid):
        schema("  nrtd   ")

    test_str = "This is a test including uiae."
    assert schema(test_str) == test_str


def test_is_regex() -> None:
    """Test the is_regex validator."""
    schema = vol.Schema(cv.is_regex)

    with pytest.raises(vol.Invalid):
        schema("(")

    with pytest.raises(vol.Invalid):
        schema({"a dict": "is not a regex"})

    valid_re = ".*"
    schema(valid_re)


def test_comp_entity_ids() -> None:
    """Test config validation for component entity IDs."""
    schema = vol.Schema(cv.comp_entity_ids)

    for valid in (
        "ALL",
        "all",
        "AlL",
        "light.kitchen",
        ["light.kitchen"],
        ["light.kitchen", "light.ceiling"],
        [],
    ):
        schema(valid)

    for invalid in (["light.kitchen", "not-entity-id"], "*", ""):
        with pytest.raises(vol.Invalid):
            schema(invalid)


def test_uuid4_hex(caplog: pytest.LogCaptureFixture) -> None:
    """Test uuid validation."""
    schema = vol.Schema(cv.uuid4_hex)

    for value in ("Not a hex string", "0", 0):
        with pytest.raises(vol.Invalid):
            schema(value)

    with pytest.raises(vol.Invalid):
        # the 13th char should be 4
        schema("a03d31b22eee1acc9b90eec40be6ed23")

    with pytest.raises(vol.Invalid):
        # the 17th char should be 8-a
        schema("a03d31b22eee4acc7b90eec40be6ed23")

    _hex = uuid.uuid4().hex
    assert schema(_hex) == _hex
    assert schema(_hex.upper()) == _hex


def test_key_value_schemas() -> None:
    """Test key value schemas."""
    schema = vol.Schema(
        cv.key_value_schemas(
            "mode",
            {
                "number": vol.Schema({"mode": "number", "data": int}),
                "string": vol.Schema({"mode": "string", "data": str}),
            },
        )
    )

    with pytest.raises(vol.Invalid) as excinfo:
        schema(True)
    assert str(excinfo.value) == "Expected a dictionary"

    for mode in None, {"a": "dict"}, "invalid":
        with pytest.raises(vol.Invalid) as excinfo:
            schema({"mode": mode})
        assert (
            str(excinfo.value)
            == f"Unexpected value for mode: '{mode}'. Expected number, string"
        )

    with pytest.raises(vol.Invalid) as excinfo:
        schema({"mode": "number", "data": "string-value"})
    assert str(excinfo.value) == "expected int for dictionary value @ data['data']"

    with pytest.raises(vol.Invalid) as excinfo:
        schema({"mode": "string", "data": 1})
    assert str(excinfo.value) == "expected str for dictionary value @ data['data']"

    for mode, data in (("number", 1), ("string", "hello")):
        schema({"mode": mode, "data": data})


def test_key_value_schemas_with_default() -> None:
    """Test key value schemas."""
    schema = vol.Schema(
        cv.key_value_schemas(
            "mode",
            {
                "number": vol.Schema({"mode": "number", "data": int}),
                "string": vol.Schema({"mode": "string", "data": str}),
            },
            vol.Schema({"mode": cv.dynamic_template}),
            "a cool template",
        )
    )

    with pytest.raises(vol.Invalid) as excinfo:
        schema(True)
    assert str(excinfo.value) == "Expected a dictionary"

    for mode in None, {"a": "dict"}, "invalid":
        with pytest.raises(vol.Invalid) as excinfo:
            schema({"mode": mode})
        assert (
            str(excinfo.value)
            == f"Unexpected value for mode: '{mode}'. Expected number, string, a cool template"
        )

    with pytest.raises(vol.Invalid) as excinfo:
        schema({"mode": "number", "data": "string-value"})
    assert str(excinfo.value) == "expected int for dictionary value @ data['data']"

    with pytest.raises(vol.Invalid) as excinfo:
        schema({"mode": "string", "data": 1})
    assert str(excinfo.value) == "expected str for dictionary value @ data['data']"

    for mode, data in (("number", 1), ("string", "hello")):
        schema({"mode": mode, "data": data})
    schema({"mode": "{{ 1 + 1}}"})


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ({"delay": "{{ invalid"}, "should be format 'HH:MM'"),
        ({"wait_template": "{{ invalid"}, "invalid template"),
        ({"condition": "invalid"}, "Unexpected value for condition: 'invalid'"),
        (
            {"condition": "not", "conditions": {"condition": "invalid"}},
            "Unexpected value for condition: 'invalid'",
        ),
        # The validation error message could be improved to explain that this is not
        # a valid shorthand template
        (
            {"condition": "not", "conditions": "not a dynamic template"},
            "Expected a dictionary",
        ),
        (
            {"event": None},
            r"string value is None for dictionary value @ data\['event'\]",
        ),
        (
            {"device_id": None},
            r"string value is None for dictionary value @ data\['device_id'\]",
        ),
        (
            {"scene": "light.kitchen"},
            "Entity ID 'light.kitchen' does not belong to domain 'scene'",
        ),
        (
            {
                "alias": "stop step",
                "stop": "In the name of love",
                "error": True,
                "response_variable": "response-value",
            },
            "not allowed to add a response to an error stop action",
        ),
    ],
)
def test_script(caplog: pytest.LogCaptureFixture, config: dict, error: str) -> None:
    """Test script validation is user friendly."""
    with pytest.raises(vol.Invalid, match=error):
        cv.script_action(config)


def test_whitespace() -> None:
    """Test whitespace validation."""
    schema = vol.Schema(cv.whitespace)

    for value in (
        None,
        "T",
        "negative",
        "lock",
        "tr  ue",  # codespell:ignore ue
        [],
        [1, 2],
        {"one": "two"},
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("  ", "   "):
        assert schema(value)


def test_currency() -> None:
    """Test currency validator."""
    schema = vol.Schema(cv.currency)

    for value in (
        None,
        "BTC",
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("EUR", "USD"):
        assert schema(value)


def test_historic_currency() -> None:
    """Test historic currency validator."""
    schema = vol.Schema(cv.historic_currency)

    for value in (None, "BTC", "EUR"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("DEM", "NLG"):
        assert schema(value)


def test_country() -> None:
    """Test country validator."""
    schema = vol.Schema(cv.country)

    for value in (None, "Candyland", "USA"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("NL", "SE"):
        assert schema(value)


def test_language() -> None:
    """Test language validator."""
    schema = vol.Schema(cv.language)

    for value in (None, "Klingon", "english"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("en", "sv"):
        assert schema(value)


def test_positive_time_period_template() -> None:
    """Test positive time period template validation."""
    schema = vol.Schema(cv.positive_time_period_template)

    with pytest.raises(vol.MultipleInvalid):
        schema({})
    with pytest.raises(vol.MultipleInvalid):
        schema({5: 5})
    with pytest.raises(vol.MultipleInvalid):
        schema({"invalid": 5})
    with pytest.raises(vol.MultipleInvalid):
        schema("invalid")

    # Time periods pass
    schema("00:01")
    schema("00:00:01")
    schema("00:00:00.500")
    schema({"minutes": 5})

    # Templates are not evaluated and will pass
    schema("{{ 'invalid' }}")
    schema({"{{ 'invalid' }}": 5})
    schema({"minutes": "{{ 'invalid' }}"})


def test_empty_schema(caplog: pytest.LogCaptureFixture) -> None:
    """Test empty_config_schema."""
    expected_message = (
        "The test_domain integration does not support any configuration parameters"
    )

    cv.empty_config_schema("test_domain")({})
    assert expected_message not in caplog.text

    cv.empty_config_schema("test_domain")({"test_domain": {}})
    assert expected_message not in caplog.text

    cv.empty_config_schema("test_domain")({"test_domain": {"foo": "bar"}})
    assert expected_message in caplog.text


def test_empty_schema_cant_find_module() -> None:
    """Test if the current module cannot be inspected."""
    cv.empty_config_schema("test_domain")({"test_domain": {"foo": "bar"}})


def test_config_entry_only_schema(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test config_entry_only_config_schema."""
    expected_issue = "config_entry_only_test_domain"
    expected_message = (
        "The test_domain integration does not support YAML setup, please remove "
        "it from your configuration"
    )

    cv.config_entry_only_config_schema("test_domain")({})
    assert expected_message not in caplog.text
    assert not issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, expected_issue)

    cv.config_entry_only_config_schema("test_domain")({"test_domain": {}})
    assert expected_message in caplog.text
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, expected_issue)
    issue_registry.async_delete(HOMEASSISTANT_DOMAIN, expected_issue)

    cv.config_entry_only_config_schema("test_domain")({"test_domain": {"foo": "bar"}})
    assert expected_message in caplog.text
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, expected_issue)


def test_config_entry_only_schema_cant_find_module() -> None:
    """Test if the current module cannot be inspected."""
    cv.config_entry_only_config_schema("test_domain")({"test_domain": {"foo": "bar"}})


def test_config_entry_only_schema_no_hass(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test if the hass context is not set in our context."""
    with patch(
        "homeassistant.helpers.config_validation.async_get_hass",
        side_effect=HomeAssistantError,
    ):
        cv.config_entry_only_config_schema("test_domain")(
            {"test_domain": {"foo": "bar"}}
        )
    expected_message = (
        "The test_domain integration does not support YAML setup, please remove "
        "it from your configuration"
    )
    assert expected_message in caplog.text
    assert not issue_registry.issues


def test_platform_only_schema(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test config_entry_only_config_schema."""
    expected_issue = "platform_only_test_domain"
    expected_message = (
        "The test_domain integration does not support YAML setup, please remove "
        "it from your configuration"
    )
    cv.platform_only_config_schema("test_domain")({})
    assert expected_message not in caplog.text
    assert not issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, expected_issue)

    cv.platform_only_config_schema("test_domain")({"test_domain": {}})
    assert expected_message in caplog.text
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, expected_issue)
    issue_registry.async_delete(HOMEASSISTANT_DOMAIN, expected_issue)

    cv.platform_only_config_schema("test_domain")({"test_domain": {"foo": "bar"}})
    assert expected_message in caplog.text
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, expected_issue)


def test_domain() -> None:
    """Test domain."""
    with pytest.raises(vol.Invalid):
        cv.domain_key(5)
    with pytest.raises(vol.Invalid):
        cv.domain_key("")
    with pytest.raises(vol.Invalid):
        cv.domain_key("hue ")
    with pytest.raises(vol.Invalid):
        cv.domain_key("hue  ")
    assert cv.domain_key("hue") == "hue"
    assert cv.domain_key("hue1") == "hue1"
    assert cv.domain_key("hue 1") == "hue"
    assert cv.domain_key("hue  1") == "hue"


def test_color_hex() -> None:
    """Test color validation in hex format."""
    assert cv.color_hex("#123456") == "#123456"
    assert cv.color_hex("#FFaaFF") == "#FFaaFF"
    assert cv.color_hex("#FFFFFF") == "#FFFFFF"
    assert cv.color_hex("#000000") == "#000000"

    msg = r"Color should be in the format #RRGGBB"
    with pytest.raises(vol.Invalid, match=msg):
        cv.color_hex("#777")

    with pytest.raises(vol.Invalid, match=msg):
        cv.color_hex("FFFFF")

    with pytest.raises(vol.Invalid, match=msg):
        cv.color_hex("FFFFFF")

    with pytest.raises(vol.Invalid, match=msg):
        cv.color_hex("#FFFFFFF")

    with pytest.raises(vol.Invalid, match=msg):
        cv.color_hex(123456)


def test_determine_script_action_ambiguous() -> None:
    """Test determine script action with ambiguous actions."""
    assert (
        cv.determine_script_action(
            {
                "type": "is_power",
                "condition": "device",
                "device_id": "9c2bda81bc7997c981f811c32cafdb22",
                "entity_id": "2ee287ec70dd0c6db187b539bee429b7",
                "domain": "sensor",
                "below": "15",
            }
        )
        == "condition"
    )


def test_determine_script_action_non_ambiguous() -> None:
    """Test determine script action with a non ambiguous action."""
    assert cv.determine_script_action({"delay": "00:00:05"}) == "delay"


async def test_async_validate(hass: HomeAssistant, tmpdir: py.path.local) -> None:
    """Test the async_validate helper."""
    validator_calls: dict[str, list[int]] = {}

    def _mock_validator_schema(real_func, *args):
        calls = validator_calls.setdefault(real_func.__name__, [])
        calls.append(threading.get_ident())
        return real_func(*args)

    CV_PREFIX = "homeassistant.helpers.config_validation"
    with (
        patch(f"{CV_PREFIX}.isdir", wraps=partial(_mock_validator_schema, cv.isdir)),
        patch(f"{CV_PREFIX}.string", wraps=partial(_mock_validator_schema, cv.string)),
    ):
        # Assert validation in event loop when not decorated with not_async_friendly
        await cv.async_validate(hass, cv.string, "abcd")
        assert validator_calls == {"string": [hass.loop_thread_id]}
        validator_calls = {}

        # Assert validation in executor when decorated with not_async_friendly
        await cv.async_validate(hass, cv.isdir, tmpdir)
        assert validator_calls == {"isdir": [hass.loop_thread_id, ANY]}
        assert validator_calls["isdir"][1] != hass.loop_thread_id
        validator_calls = {}

        # Assert validation in executor when decorated with not_async_friendly
        await cv.async_validate(hass, vol.All(cv.isdir, cv.string), tmpdir)
        assert validator_calls == {"isdir": [hass.loop_thread_id, ANY], "string": [ANY]}
        assert validator_calls["isdir"][1] != hass.loop_thread_id
        assert validator_calls["string"][0] != hass.loop_thread_id
        validator_calls = {}

        # Assert validation in executor when decorated with not_async_friendly
        await cv.async_validate(hass, vol.All(cv.string, cv.isdir), tmpdir)
        assert validator_calls == {
            "isdir": [hass.loop_thread_id, ANY],
            "string": [hass.loop_thread_id, ANY],
        }
        assert validator_calls["isdir"][1] != hass.loop_thread_id
        assert validator_calls["string"][1] != hass.loop_thread_id
        validator_calls = {}

        # Assert validation in event loop when not using cv.async_validate
        cv.isdir(tmpdir)
        assert validator_calls == {"isdir": [hass.loop_thread_id]}
        validator_calls = {}

        # Assert validation in event loop when not using cv.async_validate
        vol.All(cv.isdir, cv.string)(tmpdir)
        assert validator_calls == {
            "isdir": [hass.loop_thread_id],
            "string": [hass.loop_thread_id],
        }
        validator_calls = {}

        # Assert validation in event loop when not using cv.async_validate
        vol.All(cv.string, cv.isdir)(tmpdir)
        assert validator_calls == {
            "isdir": [hass.loop_thread_id],
            "string": [hass.loop_thread_id],
        }
        validator_calls = {}


async def test_is_entity_service_schema(
    hass: HomeAssistant,
) -> None:
    """Test cv.is_entity_service_schema."""
    for schema in (
        vol.Schema({"some": str}),
        vol.All(vol.Schema({"some": str})),
        vol.Any(vol.Schema({"some": str})),
        vol.Any(cv.make_entity_service_schema({"some": str})),
    ):
        assert cv.is_entity_service_schema(schema) is False

    for schema in (
        cv.make_entity_service_schema({"some": str}),
        vol.Schema(cv.make_entity_service_schema({"some": str})),
        vol.Schema(vol.All(cv.make_entity_service_schema({"some": str}))),
        vol.Schema(vol.Schema(cv.make_entity_service_schema({"some": str}))),
        vol.All(cv.make_entity_service_schema({"some": str})),
        vol.All(vol.All(cv.make_entity_service_schema({"some": str}))),
        vol.All(vol.Schema(cv.make_entity_service_schema({"some": str}))),
    ):
        assert cv.is_entity_service_schema(schema) is True
