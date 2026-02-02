"""Test Home Assistant template helper methods."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import json
import logging
import math
import random
from unittest.mock import patch

from freezegun import freeze_time
import orjson
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import group
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfArea,
    UnitOfLength,
    UnitOfMass,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import entity, entity_registry as er, template, translation
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.template.render_info import (
    ALL_STATES_RATE_LIMIT,
    DOMAIN_STATES_RATE_LIMIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import UnitSystem

from .helpers import assert_result_info, render, render_to_info

from tests.common import MockConfigEntry, async_fire_time_changed


def _set_up_units(hass: HomeAssistant) -> None:
    """Set up the tests."""
    hass.config.units = UnitSystem(
        "custom",
        accumulated_precipitation=UnitOfPrecipitationDepth.MILLIMETERS,
        area=UnitOfArea.SQUARE_METERS,
        conversions={},
        length=UnitOfLength.METERS,
        mass=UnitOfMass.GRAMS,
        pressure=UnitOfPressure.PA,
        temperature=UnitOfTemperature.CELSIUS,
        volume=UnitOfVolume.LITERS,
        wind_speed=UnitOfSpeed.KILOMETERS_PER_HOUR,
    )


async def test_template_render_missing_hass(hass: HomeAssistant) -> None:
    """Test template render when hass is not set."""
    hass.states.async_set("sensor.test", "23")
    template_obj = template.Template("{{ states('sensor.test') }}", None)
    template.render_info_cv.set(template.RenderInfo(template_obj))

    with pytest.raises(RuntimeError, match="hass not set while rendering"):
        template_obj.async_render_to_info()


async def test_template_render_info_collision(hass: HomeAssistant) -> None:
    """Test template render info collision.

    This usually means the template is being rendered
    in the wrong thread.
    """
    hass.states.async_set("sensor.test", "23")
    template_obj = template.Template("{{ states('sensor.test') }}", None)
    template_obj.hass = hass
    template.render_info_cv.set(template.RenderInfo(template_obj))

    with pytest.raises(RuntimeError, match="RenderInfo already set while rendering"):
        template_obj.async_render_to_info()


@pytest.mark.usefixtures("hass")
def test_template_equality() -> None:
    """Test template comparison and hashing."""
    template_one = template.Template("{{ template_one }}")
    template_one_1 = template.Template("{{ template_one }}")
    template_two = template.Template("{{ template_two }}")

    assert template_one == template_one_1
    assert template_one != template_two
    assert hash(template_one) == hash(template_one_1)
    assert hash(template_one) != hash(template_two)

    assert str(template_one_1) == "Template<template=({{ template_one }}) renders=0>"

    with pytest.raises(TypeError):
        template.Template(["{{ template_one }}"])


def test_invalid_template(hass: HomeAssistant) -> None:
    """Invalid template raises error."""
    tmpl = template.Template("{{", hass)

    with pytest.raises(TemplateError):
        tmpl.ensure_valid()

    with pytest.raises(TemplateError):
        tmpl.async_render()

    info = tmpl.async_render_to_info()
    with pytest.raises(TemplateError):
        assert info.result() == "impossible"

    tmpl = template.Template("{{states(keyword)}}", hass)

    tmpl.ensure_valid()

    with pytest.raises(TemplateError):
        tmpl.async_render()


def test_referring_states_by_entity_id(hass: HomeAssistant) -> None:
    """Test referring states by entity id."""
    hass.states.async_set("test.object", "happy")
    assert render(hass, "{{ states.test.object.state }}") == "happy"

    assert render(hass, '{{ states["test.object"].state }}') == "happy"

    assert render(hass, '{{ states("test.object") }}') == "happy"


def test_invalid_entity_id(hass: HomeAssistant) -> None:
    """Test referring states by entity id."""
    with pytest.raises(TemplateError):
        render(hass, '{{ states["big.fat..."] }}')
    with pytest.raises(TemplateError):
        render(hass, '{{ states.test["big.fat..."] }}')
    with pytest.raises(TemplateError):
        render(hass, '{{ states["invalid/domain"] }}')


def test_raise_exception_on_error(hass: HomeAssistant) -> None:
    """Test raising an exception on error."""
    with pytest.raises(TemplateError):
        template.Template("{{ invalid_syntax").ensure_valid()


def test_iterating_all_states(hass: HomeAssistant) -> None:
    """Test iterating all states."""
    tmpl_str = "{% for state in states | sort(attribute='entity_id') %}{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "", all_states=True)
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "happy")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "10happy", entities=[], all_states=True)


def test_iterating_all_states_unavailable(hass: HomeAssistant) -> None:
    """Test iterating all states unavailable."""
    hass.states.async_set("test.object", "on")

    tmpl_str = (
        "{{"
        "  states"
        "  | selectattr('state', 'in', ['unavailable', 'unknown', 'none'])"
        "  | list"
        "  | count"
        "}}"
    )

    info = render_to_info(hass, tmpl_str)

    assert info.all_states is True
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "unknown")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, 1, entities=[], all_states=True)


def test_iterating_domain_states(hass: HomeAssistant) -> None:
    """Test iterating domain states."""
    tmpl_str = "{% for state in states.sensor %}{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "", domains=["sensor"])
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "happy")
    hass.states.async_set("sensor.back_door", "open")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(
        info,
        "open10",
        entities=[],
        domains=["sensor"],
    )


async def test_import(hass: HomeAssistant) -> None:
    """Test that imports work from the config/custom_templates folder."""
    await template.async_load_custom_templates(hass)
    assert "test.jinja" in template._get_hass_loader(hass).sources
    assert "inner/inner_test.jinja" in template._get_hass_loader(hass).sources
    assert (
        render(
            hass,
            """
        {% import 'test.jinja' as t %}
        {{ t.test_macro() }} {{ t.test_variable }}
        """,
        )
        == "macro variable"
    )

    assert (
        render(
            hass,
            """
        {% import 'inner/inner_test.jinja' as t %}
        {{ t.test_macro() }} {{ t.test_variable }}
        """,
        )
        == "inner macro inner variable"
    )

    with pytest.raises(TemplateError):
        render(
            hass,
            """
        {% import 'notfound.jinja' as t %}
        {{ t.test_macro() }} {{ t.test_variable }}
        """,
        )


async def test_import_change(hass: HomeAssistant) -> None:
    """Test that a change in HassLoader results in updated imports."""
    await template.async_load_custom_templates(hass)
    to_test = template.Template(
        """
        {% import 'test.jinja' as t %}
        {{ t.test_macro() }} {{ t.test_variable }}
        """,
        hass,
    )
    assert to_test.async_render() == "macro variable"

    template._get_hass_loader(hass).sources = {
        "test.jinja": """
            {% macro test_macro() -%}
            macro2
            {%- endmacro %}

            {% set test_variable = "variable2" %}
            """
    }
    assert to_test.async_render() == "macro2 variable2"


def test_loop_controls(hass: HomeAssistant) -> None:
    """Test that loop controls are enabled."""
    tpl = """
    {%- for v in range(10) %}
        {%- if v == 1 -%}
            {%- continue -%}
        {%- elif v == 3 -%}
            {%- break -%}
        {%- endif -%}
        {{ v }}
    {%- endfor -%}
    """
    assert render(hass, tpl) == "02"


def test_float_function(hass: HomeAssistant) -> None:
    """Test float function."""
    hass.states.async_set("sensor.temperature", "12")

    assert render(hass, "{{ float(states.sensor.temperature.state) }}") == 12.0

    assert render(hass, "{{ float(states.sensor.temperature.state) > 11 }}") is True

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ float('forgiving') }}")

    # Test handling of default return value
    assert render(hass, "{{ float('bad', 1) }}") == 1
    assert render(hass, "{{ float('bad', default=1) }}") == 1


def test_float_filter(hass: HomeAssistant) -> None:
    """Test float filter."""
    hass.states.async_set("sensor.temperature", "12")

    assert render(hass, "{{ states.sensor.temperature.state | float }}") == 12.0
    assert render(hass, "{{ states.sensor.temperature.state | float > 11 }}") is True

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'bad' | float }}")

    # Test handling of default return value
    assert render(hass, "{{ 'bad' | float(1) }}") == 1
    assert render(hass, "{{ 'bad' | float(default=1) }}") == 1


def test_int_filter(hass: HomeAssistant) -> None:
    """Test int filter."""
    hass.states.async_set("sensor.temperature", "12.2")
    assert render(hass, "{{ states.sensor.temperature.state | int }}") == 12
    assert render(hass, "{{ states.sensor.temperature.state | int > 11 }}") is True

    hass.states.async_set("sensor.temperature", "0x10")
    assert render(hass, "{{ states.sensor.temperature.state | int(base=16) }}") == 16

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'bad' | int }}")

    # Test handling of default return value
    assert render(hass, "{{ 'bad' | int(1) }}") == 1
    assert render(hass, "{{ 'bad' | int(default=1) }}") == 1


def test_int_function(hass: HomeAssistant) -> None:
    """Test int filter."""
    hass.states.async_set("sensor.temperature", "12.2")
    assert render(hass, "{{ int(states.sensor.temperature.state) }}") == 12
    assert render(hass, "{{ int(states.sensor.temperature.state) > 11 }}") is True

    hass.states.async_set("sensor.temperature", "0x10")
    assert render(hass, "{{ int(states.sensor.temperature.state, base=16) }}") == 16

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ int('bad') }}")

    # Test handling of default return value
    assert render(hass, "{{ int('bad', 1) }}") == 1
    assert render(hass, "{{ int('bad', default=1) }}") == 1


def test_bool_function(hass: HomeAssistant) -> None:
    """Test bool function."""
    assert render(hass, "{{ bool(true) }}") is True
    assert render(hass, "{{ bool(false) }}") is False
    assert render(hass, "{{ bool('on') }}") is True
    assert render(hass, "{{ bool('off') }}") is False
    with pytest.raises(TemplateError):
        render(hass, "{{ bool('unknown') }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ bool(none) }}")
    assert render(hass, "{{ bool('unavailable', none) }}") is None
    assert render(hass, "{{ bool('unavailable', default=none) }}") is None


def test_bool_filter(hass: HomeAssistant) -> None:
    """Test bool filter."""
    assert render(hass, "{{ true | bool }}") is True
    assert render(hass, "{{ false | bool }}") is False
    assert render(hass, "{{ 'on' | bool }}") is True
    assert render(hass, "{{ 'off' | bool }}") is False
    with pytest.raises(TemplateError):
        render(hass, "{{ 'unknown' | bool }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ none | bool }}")
    assert render(hass, "{{ 'unavailable' | bool(none) }}") is None
    assert render(hass, "{{ 'unavailable' | bool(default=none) }}") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True),
        (0.0, True),
        ("0", True),
        ("0.0", True),
        (True, True),
        (False, True),
        ("True", False),
        ("False", False),
        (None, False),
        ("None", False),
        ("horse", False),
        (math.pi, True),
        (math.nan, False),
        (math.inf, False),
        ("nan", False),
        ("inf", False),
    ],
)
def test_isnumber(hass: HomeAssistant, value, expected) -> None:
    """Test is_number."""
    assert render(hass, "{{ is_number(value) }}", {"value": value}) == expected
    assert render(hass, "{{ value | is_number }}", {"value": value}) == expected
    assert render(hass, "{{ value is is_number }}", {"value": value}) == expected


def test_converting_datetime_to_iterable(hass: HomeAssistant) -> None:
    """Test converting a datetime to an iterable raises an error."""
    dt_ = datetime(2020, 1, 1, 0, 0, 0)
    with pytest.raises(TemplateError):
        render(hass, "{{ tuple(value) }}", {"value": dt_})
    with pytest.raises(TemplateError):
        render(hass, "{{ set(value) }}", {"value": dt_})


def test_rounding_value(hass: HomeAssistant) -> None:
    """Test rounding value."""
    hass.states.async_set("sensor.temperature", 12.78)

    assert render(hass, "{{ states.sensor.temperature.state | round(1) }}") == 12.8

    assert (
        render(hass, "{{ states.sensor.temperature.state | multiply(10) | round }}")
        == 128
    )

    assert (
        render(hass, '{{ states.sensor.temperature.state | round(1, "floor") }}')
        == 12.7
    )

    assert (
        render(hass, '{{ states.sensor.temperature.state | round(1, "ceil") }}') == 12.8
    )

    assert (
        render(hass, '{{ states.sensor.temperature.state | round(1, "half") }}') == 13.0
    )


def test_rounding_value_on_error(hass: HomeAssistant) -> None:
    """Test rounding value handling of error."""
    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ None | round }}")

    with pytest.raises(TemplateError):
        render(hass, '{{ "no_number" | round }}')

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | round(default=1) }}") == 1


def test_multiply(hass: HomeAssistant) -> None:
    """Test multiply."""
    tests = {10: 100}

    for inp, out in tests.items():
        assert render(hass, f"{{{{ {inp} | multiply(10) | round }}}}") == out

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ abcd | multiply(10) }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | multiply(10, 1) }}") == 1
    assert render(hass, "{{ 'no_number' | multiply(10, default=1) }}") == 1


def test_add(hass: HomeAssistant) -> None:
    """Test add."""
    tests = {10: 42}

    for inp, out in tests.items():
        assert render(hass, f"{{{{ {inp} | add(32) | round }}}}") == out

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ abcd | add(10) }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | add(10, 1) }}") == 1
    assert render(hass, "{{ 'no_number' | add(10, default=1) }}") == 1


def test_apply(hass: HomeAssistant) -> None:
    """Test apply."""
    tpl = """
    {%- macro add_foo(arg) -%}
    {{arg}}foo
    {%- endmacro -%}
    {{ ["a", "b", "c"] | map('apply', add_foo) | list }}
    """
    assert render(hass, tpl) == ["afoo", "bfoo", "cfoo"]

    assert render(
        hass, "{{ ['1', '2', '3', '4', '5'] | map('apply', int) | list }}"
    ) == [1, 2, 3, 4, 5]


def test_apply_macro_with_arguments(hass: HomeAssistant) -> None:
    """Test apply macro with positional, named, and mixed arguments."""
    # Test macro with positional arguments
    tpl = """
                {%- macro add_numbers(a, b, c) -%}
                {{ a + b + c }}
                {%- endmacro -%}
                {{ apply(5, add_numbers, 10, 15) }}
                """
    assert render(hass, tpl) == 30

    # Test macro with named arguments
    tpl = """
                {%- macro greet(name, greeting="Hello") -%}
                {{ greeting }}, {{ name }}!
                {%- endmacro -%}
                {{ apply("World", greet, greeting="Hi") }}
                """
    assert render(hass, tpl) == "Hi, World!"

    # Test macro with mixed arguments
    tpl = """
                {%- macro format_message(prefix, name, suffix="!") -%}
                {{ prefix }} {{ name }}{{ suffix }}
                {%- endmacro -%}
                {{ apply("Welcome", format_message, "John", suffix="...") }}
                """
    assert render(hass, tpl) == "Welcome John..."


def test_as_function(hass: HomeAssistant) -> None:
    """Test as_function."""
    tpl = """
        {%- macro macro_double(num, returns) -%}
        {%- do returns(num * 2) -%}
        {%- endmacro -%}
        {%- set double = macro_double | as_function -%}
        {{ double(5) }}
        """
    assert render(hass, tpl) == 10


def test_as_function_no_arguments(hass: HomeAssistant) -> None:
    """Test as_function with no arguments."""
    tpl = """
        {%- macro macro_get_hello(returns) -%}
        {%- do returns("Hello") -%}
        {%- endmacro -%}
        {%- set get_hello = macro_get_hello | as_function -%}
        {{ get_hello() }}
        """
    assert render(hass, tpl) == "Hello"


def test_to_json(hass: HomeAssistant) -> None:
    """Test the object to JSON string filter."""

    # Note that we're not testing the actual json.loads and json.dumps methods,
    # only the filters, so we don't need to be exhaustive with our sample JSON.
    expected_result = {"Foo": "Bar"}
    actual_result = render(hass, "{{ {'Foo': 'Bar'} | to_json }}")
    assert actual_result == expected_result

    expected_result = orjson.dumps({"Foo": "Bar"}, option=orjson.OPT_INDENT_2).decode()
    actual_result = render(
        hass, "{{ {'Foo': 'Bar'} | to_json(pretty_print=True) }}", parse_result=False
    )
    assert actual_result == expected_result

    expected_result = orjson.dumps(
        {"Z": 26, "A": 1, "M": 13}, option=orjson.OPT_SORT_KEYS
    ).decode()
    actual_result = render(
        hass,
        "{{ {'Z': 26, 'A': 1, 'M': 13} | to_json(sort_keys=True) }}",
        parse_result=False,
    )
    assert actual_result == expected_result

    with pytest.raises(TemplateError):
        render(hass, "{{ {'Foo': now()} | to_json }}")

    # Test special case where substring class cannot be rendered
    # See: https://github.com/ijl/orjson/issues/445
    class MyStr(str):
        __slots__ = ()

    expected_result = '{"mykey1":11.0,"mykey2":"myvalue2","mykey3":["opt3b","opt3a"]}'
    test_dict = {
        MyStr("mykey2"): "myvalue2",
        MyStr("mykey1"): 11.0,
        MyStr("mykey3"): ["opt3b", "opt3a"],
    }
    actual_result = render(
        hass,
        "{{ test_dict | to_json(sort_keys=True) }}",
        {"test_dict": test_dict},
        parse_result=False,
    )
    assert actual_result == expected_result


def test_to_json_ensure_ascii(hass: HomeAssistant) -> None:
    """Test the object to JSON string filter."""

    # Note that we're not testing the actual json.loads and json.dumps methods,
    # only the filters, so we don't need to be exhaustive with our sample JSON.
    actual_value_ascii = render(hass, "{{ 'Bar ҝ éèà' | to_json(ensure_ascii=True) }}")
    assert actual_value_ascii == '"Bar \\u049d \\u00e9\\u00e8\\u00e0"'
    actual_value = render(hass, "{{ 'Bar ҝ éèà' | to_json(ensure_ascii=False) }}")
    assert actual_value == '"Bar ҝ éèà"'

    expected_result = json.dumps({"Foo": "Bar"}, indent=2)
    actual_result = render(
        hass,
        "{{ {'Foo': 'Bar'} | to_json(pretty_print=True, ensure_ascii=True) }}",
        parse_result=False,
    )
    assert actual_result == expected_result

    expected_result = json.dumps({"Z": 26, "A": 1, "M": 13}, sort_keys=True)
    actual_result = render(
        hass,
        "{{ {'Z': 26, 'A': 1, 'M': 13} | to_json(sort_keys=True, ensure_ascii=True) }}",
        parse_result=False,
    )
    assert actual_result == expected_result


def test_from_json(hass: HomeAssistant) -> None:
    """Test the JSON string to object filter."""

    # Note that we're not testing the actual json.loads and json.dumps methods,
    # only the filters, so we don't need to be exhaustive with our sample JSON.
    expected_result = "Bar"
    actual_result = render(hass, '{{ (\'{"Foo": "Bar"}\' | from_json).Foo }}')
    assert actual_result == expected_result

    info = render_to_info(hass, "{{ 'garbage string' | from_json }}")
    with pytest.raises(TemplateError, match="no default was specified"):
        info.result()

    actual_result = render(hass, "{{ 'garbage string' | from_json('Bar') }}")
    assert actual_result == expected_result


def test_ord(hass: HomeAssistant) -> None:
    """Test the ord filter."""
    assert render(hass, '{{ "d" | ord }}') == 100


def test_from_hex(hass: HomeAssistant) -> None:
    """Test the fromhex filter."""
    assert render(hass, "{{ '0F010003' | from_hex }}") == b"\x0f\x01\x00\x03"


@patch.object(random, "choice")
def test_random_every_time(test_choice, hass: HomeAssistant) -> None:
    """Ensure the random filter runs every time, not just once."""
    tpl = template.Template("{{ [1,2] | random }}", hass)
    test_choice.return_value = "foo"
    assert tpl.async_render() == "foo"
    test_choice.return_value = "bar"
    assert tpl.async_render() == "bar"


def test_passing_vars_as_keywords(hass: HomeAssistant) -> None:
    """Test passing variables as keywords."""
    assert render(hass, "{{ hello }}", hello=127) == 127


def test_passing_vars_as_vars(hass: HomeAssistant) -> None:
    """Test passing variables as variables."""
    assert render(hass, "{{ hello }}", {"hello": 127}) == 127


def test_passing_vars_as_list(hass: HomeAssistant) -> None:
    """Test passing variables as list."""
    assert template.render_complex(
        template.Template("{{ hello }}", hass), {"hello": ["foo", "bar"]}
    ) == ["foo", "bar"]


def test_passing_vars_as_list_element(hass: HomeAssistant) -> None:
    """Test passing variables as list."""
    tpl = template.Template("{{ hello[1] }}", hass)
    assert template.render_complex(tpl, {"hello": ["foo", "bar"]}) == "bar"


def test_passing_vars_as_dict_element(hass: HomeAssistant) -> None:
    """Test passing variables as list."""
    tpl = template.Template("{{ hello.foo }}", hass)
    assert template.render_complex(tpl, {"hello": {"foo": "bar"}}) == "bar"


def test_passing_vars_as_dict(hass: HomeAssistant) -> None:
    """Test passing variables as list."""
    tpl = template.Template("{{ hello }}", hass)
    assert template.render_complex(tpl, {"hello": {"foo": "bar"}}) == {"foo": "bar"}


def test_render_with_possible_json_value_with_valid_json(hass: HomeAssistant) -> None:
    """Render with possible JSON value with valid JSON."""
    tpl = template.Template("{{ value_json.hello }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}') == "world"


def test_render_with_possible_json_value_with_invalid_json(hass: HomeAssistant) -> None:
    """Render with possible JSON value with invalid JSON."""
    tpl = template.Template("{{ value_json }}", hass)
    assert tpl.async_render_with_possible_json_value("{ I AM NOT JSON }") == ""


def test_render_with_possible_json_value_with_template_error_value(
    hass: HomeAssistant,
) -> None:
    """Render with possible JSON value with template error value."""
    tpl = template.Template("{{ non_existing.variable }}", hass)
    assert tpl.async_render_with_possible_json_value("hello", "-") == "-"


def test_render_with_possible_json_value_with_missing_json_value(
    hass: HomeAssistant,
) -> None:
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template("{{ value_json.goodbye }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}') == ""


def test_render_with_possible_json_value_valid_with_is_defined(
    hass: HomeAssistant,
) -> None:
    """Render with possible JSON value with known JSON object."""
    tpl = template.Template("{{ value_json.hello|is_defined }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}') == "world"


def test_render_with_possible_json_value_undefined_json(hass: HomeAssistant) -> None:
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template("{{ value_json.bye|is_defined }}", hass)
    assert (
        tpl.async_render_with_possible_json_value('{"hello": "world"}')
        == '{"hello": "world"}'
    )


def test_render_with_possible_json_value_undefined_json_error_value(
    hass: HomeAssistant,
) -> None:
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template("{{ value_json.bye|is_defined }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}', "") == ""


def test_render_with_possible_json_value_non_string_value(hass: HomeAssistant) -> None:
    """Render with possible JSON value with non-string value."""
    tpl = template.Template(
        """{{ strptime(value~'+0000', '%Y-%m-%d %H:%M:%S%z') }}""",
        hass,
    )
    value = datetime(2019, 1, 18, 12, 13, 14)
    expected = str(value.replace(tzinfo=dt_util.UTC))
    assert tpl.async_render_with_possible_json_value(value) == expected


def test_render_with_possible_json_value_and_parse_result(hass: HomeAssistant) -> None:
    """Render with possible JSON value with valid JSON."""
    tpl = template.Template("{{ value_json.hello }}", hass)
    result = tpl.async_render_with_possible_json_value(
        """{"hello": {"world": "value1"}}""", parse_result=True
    )
    assert isinstance(result, dict)


def test_render_with_possible_json_value_and_dont_parse_result(
    hass: HomeAssistant,
) -> None:
    """Render with possible JSON value with valid JSON."""
    tpl = template.Template("{{ value_json.hello }}", hass)
    result = tpl.async_render_with_possible_json_value(
        """{"hello": {"world": "value1"}}""", parse_result=False
    )
    assert isinstance(result, str)


def test_if_state_exists(hass: HomeAssistant) -> None:
    """Test if state exists works."""
    hass.states.async_set("test.object", "available")

    result = render(
        hass, "{% if states.test.object %}exists{% else %}not exists{% endif %}"
    )
    assert result == "exists"


def test_is_hidden_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test is_hidden_entity method."""
    hidden_entity = entity_registry.async_get_or_create(
        "sensor", "mock", "hidden", hidden_by=er.RegistryEntryHider.USER
    )
    visible_entity = entity_registry.async_get_or_create("sensor", "mock", "visible")
    assert render(hass, f"{{{{ is_hidden_entity('{hidden_entity.entity_id}') }}}}")

    assert not render(hass, f"{{{{ is_hidden_entity('{visible_entity.entity_id}') }}}}")

    assert not render(
        hass,
        f"{{{{ ['{visible_entity.entity_id}'] | select('is_hidden_entity') | first }}}}",
    )


def test_is_state(hass: HomeAssistant) -> None:
    """Test is_state method."""
    hass.states.async_set("test.object", "available")

    result = render(
        hass, '{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}'
    )
    assert result == "yes"

    result = render(hass, """{{ is_state("test.noobject", "available") }}""")
    assert result is False

    result = render(
        hass,
        '{% if "test.object" is is_state("available") %}yes{% else %}no{% endif %}',
    )
    assert result == "yes"

    result = render(
        hass,
        """{{ ['test.object'] | select("is_state", "available") | first | default }}""",
    )
    assert result == "test.object"

    result = render(hass, '{{ is_state("test.object", ["on", "off", "available"]) }}')
    assert result is True


def test_is_state_attr(hass: HomeAssistant) -> None:
    """Test is_state_attr method."""
    hass.states.async_set("test.object", "available", {"mode": "on", "exists": None})

    result = render(
        hass,
        """{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(hass, """{{ is_state_attr("test.noobject", "mode", "on") }}""")
    assert result is False

    result = render(
        hass,
        """{% if "test.object" is is_state_attr("mode", "on") %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(
        hass,
        """{{ ['test.object'] | select("is_state_attr", "mode", "on") | first | default }}""",
    )
    assert result == "test.object"

    result = render(
        hass,
        """{% if is_state_attr("test.object", "exists", None) %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(
        hass,
        """{% if is_state_attr("test.object", "noexist", None) %}yes{% else %}no{% endif %}""",
    )
    assert result == "no"


def test_state_attr(hass: HomeAssistant) -> None:
    """Test state_attr method."""
    hass.states.async_set(
        "test.object", "available", {"effect": "action", "mode": "on"}
    )

    result = render(
        hass,
        """{% if state_attr("test.object", "mode") == "on" %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(hass, """{{ state_attr("test.noobject", "mode") == None }}""")
    assert result is True

    result = render(
        hass,
        """{% if "test.object" | state_attr("mode") == "on" %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(
        hass,
        """{{ ['test.object'] | map("state_attr", "effect") | first | default }}""",
    )
    assert result == "action"


def test_states_function(hass: HomeAssistant) -> None:
    """Test using states as a function."""
    hass.states.async_set("test.object", "available")

    result = render(hass, '{{ states("test.object") }}')
    assert result == "available"

    result = render(hass, '{{ states("test.object2") }}')
    assert result == "unknown"

    result = render(
        hass,
        """{% if "test.object" | states == "available" %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(hass, """{{ ['test.object'] | map("states") | first | default }}""")
    assert result == "available"


async def test_state_translated(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test state_translated method."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "group",
                "name": "Grouped",
                "entities": ["binary_sensor.first", "binary_sensor.second"],
            }
        },
    )
    await hass.async_block_till_done()
    await translation._async_get_translations_cache(hass).async_load("en", set())

    hass.states.async_set("switch.without_translations", "on", attributes={})
    hass.states.async_set("binary_sensor.without_device_class", "on", attributes={})
    hass.states.async_set(
        "binary_sensor.with_device_class", "on", attributes={"device_class": "motion"}
    )
    hass.states.async_set(
        "binary_sensor.with_unknown_device_class",
        "on",
        attributes={"device_class": "unknown_class"},
    )
    hass.states.async_set(
        "some_domain.with_device_class_1",
        "off",
        attributes={"device_class": "some_device_class"},
    )
    hass.states.async_set(
        "some_domain.with_device_class_2",
        "foo",
        attributes={"device_class": "some_device_class"},
    )
    hass.states.async_set("domain.is_unavailable", "unavailable", attributes={})
    hass.states.async_set("domain.is_unknown", "unknown", attributes={})

    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        translation_key="translation_key",
    )
    hass.states.async_set("light.hue_5678", "on", attributes={})

    result = render(hass, '{{ state_translated("switch.without_translations") }}')
    assert result == "on"

    result = render(
        hass, '{{ state_translated("binary_sensor.without_device_class") }}'
    )
    assert result == "On"

    result = render(hass, '{{ state_translated("binary_sensor.with_device_class") }}')
    assert result == "Detected"

    result = render(
        hass, '{{ state_translated("binary_sensor.with_unknown_device_class") }}'
    )
    assert result == "On"

    with pytest.raises(TemplateError):
        render(hass, '{{ state_translated("contextfunction") }}')

    result = render(hass, '{{ state_translated("switch.invalid") }}')
    assert result == "unknown"

    with pytest.raises(TemplateError):
        render(hass, '{{ state_translated("-invalid") }}')

    def mock_get_cached_translations(
        _hass: HomeAssistant,
        _language: str,
        category: str,
        _integrations: Iterable[str] | None = None,
    ):
        if category == "entity":
            return {
                "component.hue.entity.light.translation_key.state.on": "state_is_on",
            }
        return {}

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        side_effect=mock_get_cached_translations,
    ):
        result = render(hass, '{{ state_translated("light.hue_5678") }}')
        assert result == "state_is_on"

    result = render(hass, '{{ state_translated("domain.is_unavailable") }}')
    assert result == "unavailable"

    result = render(hass, '{{ state_translated("domain.is_unknown") }}')
    assert result == "unknown"


def test_has_value(hass: HomeAssistant) -> None:
    """Test has_value method."""
    hass.states.async_set("test.value1", 1)
    hass.states.async_set("test.unavailable", STATE_UNAVAILABLE)

    result = render(hass, """{{ has_value("test.value1") }}""")
    assert result is True

    result = render(hass, """{{ has_value("test.unavailable") }}""")
    assert result is False

    result = render(hass, """{{ has_value("test.unknown") }}""")
    assert result is False

    result = render(
        hass, """{% if "test.value1" is has_value %}yes{% else %}no{% endif %}"""
    )
    assert result == "yes"


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_timedelta(mock_is_safe, hass: HomeAssistant) -> None:
    """Test relative_time method."""
    now = datetime.strptime("2000-01-01 10:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
    with freeze_time(now):
        result = render(hass, "{{timedelta(seconds=120)}}")
        assert result == "0:02:00"

        result = render(hass, "{{timedelta(seconds=86400)}}")
        assert result == "1 day, 0:00:00"

        result = render(hass, "{{timedelta(days=1, hours=4)}}")
        assert result == "1 day, 4:00:00"

        result = render(hass, "{{relative_time(now() - timedelta(seconds=3600))}}")
        assert result == "1 hour"

        result = render(hass, "{{relative_time(now() - timedelta(seconds=86400))}}")
        assert result == "1 day"

        result = render(hass, "{{relative_time(now() - timedelta(seconds=86401))}}")
        assert result == "1 day"

        result = render(hass, "{{relative_time(now() - timedelta(weeks=2, days=1))}}")
        assert result == "15 days"


def test_version(hass: HomeAssistant) -> None:
    """Test version filter and function."""
    filter_result = render(hass, "{{ '2099.9.9' | version}}")
    function_result = render(hass, "{{ version('2099.9.9')}}")
    assert filter_result == function_result == "2099.9.9"

    filter_result = render(hass, "{{ '2099.9.9' | version < '2099.9.10' }}")
    function_result = render(hass, "{{ version('2099.9.9') < '2099.9.10' }}")
    assert filter_result is function_result is True

    filter_result = render(hass, "{{ '2099.9.9' | version == '2099.9.9' }}")
    function_result = render(hass, "{{ version('2099.9.9') == '2099.9.9' }}")
    assert filter_result is function_result is True

    with pytest.raises(TemplateError):
        render(hass, "{{ version(None) < '2099.9.10' }}")


def test_pack(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test struct pack method."""

    # render as filter
    variables = {"value": 0xDEADBEEF}
    assert render(hass, "{{ value | pack('>I') }}", variables) == b"\xde\xad\xbe\xef"

    # render as function
    assert render(hass, "{{ pack(value, '>I') }}", variables) == b"\xde\xad\xbe\xef"

    # test with None value
    # "Template warning: 'pack' unable to pack object with type '%s' and format_string '%s' see https://docs.python.org/3/library/struct.html for more information"
    assert render(hass, "{{ pack(value, '>I') }}", {"value": None}) is None
    assert (
        "Template warning: 'pack' unable to pack object 'None' with type 'NoneType' and"
        " format_string '>I' see https://docs.python.org/3/library/struct.html for more"
        " information" in caplog.text
    )

    # test with invalid filter
    # "Template warning: 'pack' unable to pack object with type '%s' and format_string '%s' see https://docs.python.org/3/library/struct.html for more information"
    assert render(hass, "{{ pack(value, 'invalid filter') }}", variables) is None
    assert (
        "Template warning: 'pack' unable to pack object '3735928559' with type 'int'"
        " and format_string 'invalid filter' see"
        " https://docs.python.org/3/library/struct.html for more information"
        in caplog.text
    )


def test_unpack(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test struct unpack method."""

    variables = {"value": b"\xde\xad\xbe\xef"}

    # render as filter
    result = render(hass, """{{ value | unpack('>I') }}""", variables)
    assert result == 0xDEADBEEF

    # render as function
    result = render(hass, """{{ unpack(value, '>I') }}""", variables)
    assert result == 0xDEADBEEF

    # unpack with offset
    result = render(hass, """{{ unpack(value, '>H', offset=2) }}""", variables)
    assert result == 0xBEEF

    # test with an empty bytes object
    assert render(hass, """{{ unpack(value, '>I') }}""", {"value": b""}) is None
    assert (
        "Template warning: 'unpack' unable to unpack object 'b''' with format_string"
        " '>I' and offset 0 see https://docs.python.org/3/library/struct.html for more"
        " information" in caplog.text
    )

    # test with invalid filter
    assert (
        render(hass, """{{ unpack(value, 'invalid filter') }}""", {"value": b""})
        is None
    )
    assert (
        "Template warning: 'unpack' unable to unpack object 'b''' with format_string"
        " 'invalid filter' and offset 0 see"
        " https://docs.python.org/3/library/struct.html for more information"
        in caplog.text
    )


def test_distance_function_with_1_state(hass: HomeAssistant) -> None:
    """Test distance function with 1 state."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )

    result = render(hass, "{{ distance(states.test.object) | round }}")
    assert result == 187


def test_distance_function_with_2_states(hass: HomeAssistant) -> None:
    """Test distance function with 2 states."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(
        hass, "{{ distance(states.test.object, states.test.object_2) | round }}"
    )
    assert result == 187


def test_distance_function_with_1_coord(hass: HomeAssistant) -> None:
    """Test distance function with 1 coord."""
    _set_up_units(hass)

    result = render(hass, '{{ distance("32.87336", "-117.22943") | round }}')
    assert result == 187


def test_distance_function_with_2_coords(hass: HomeAssistant) -> None:
    """Test distance function with 2 coords."""
    _set_up_units(hass)
    tpl = f'{{{{ distance("32.87336", "-117.22943", {hass.config.latitude}, {hass.config.longitude}) | round }}}}'
    assert render(hass, tpl) == 187


def test_distance_function_with_1_state_1_coord(hass: HomeAssistant) -> None:
    """Test distance function with 1 state 1 coord."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(
        hass, '{{ distance("32.87336", "-117.22943", states.test.object_2) | round }}'
    )
    assert result == 187

    result = render(
        hass, '{{ distance(states.test.object_2, "32.87336", "-117.22943") | round }}'
    )
    assert result == 187


def test_distance_function_return_none_if_invalid_state(hass: HomeAssistant) -> None:
    """Test distance function return None if invalid state."""
    hass.states.async_set("test.object_2", "happy", {"latitude": 10})
    with pytest.raises(TemplateError):
        render(hass, "{{ distance(states.test.object_2) | round }}")


def test_distance_function_return_none_if_invalid_coord(hass: HomeAssistant) -> None:
    """Test distance function return None if invalid coord."""
    assert render(hass, '{{ distance("123", "abc") }}') is None

    assert render(hass, '{{ distance("123") }}') is None

    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(hass, '{{ distance("123", states.test_object_2) }}')
    assert result is None


def test_distance_function_with_2_entity_ids(hass: HomeAssistant) -> None:
    """Test distance function with 2 entity ids."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(hass, '{{ distance("test.object", "test.object_2") | round }}')
    assert result == 187


def test_distance_function_with_1_entity_1_coord(hass: HomeAssistant) -> None:
    """Test distance function with 1 entity_id and 1 coord."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(
        hass, '{{ distance("test.object", "32.87336", "-117.22943") | round }}'
    )
    assert result == 187


def test_closest_function_home_vs_domain(hass: HomeAssistant) -> None:
    """Test closest function home vs domain."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_test_domain.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert (
        render(hass, "{{ closest(states.test_domain).entity_id }}")
        == "test_domain.object"
    )

    assert (
        render(hass, "{{ (states.test_domain | closest).entity_id }}")
        == "test_domain.object"
    )


def test_closest_function_home_vs_all_states(hass: HomeAssistant) -> None:
    """Test closest function home vs all states."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain_2.and_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert render(hass, "{{ closest(states).entity_id }}") == "test_domain_2.and_closer"

    assert (
        render(hass, "{{ (states | closest).entity_id }}") == "test_domain_2.and_closer"
    )


async def test_closest_function_home_vs_group_entity_id(hass: HomeAssistant) -> None:
    """Test closest function home vs group entity id."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_in_group.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "location group",
        created_by_service=False,
        entity_ids=["test_domain.object"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, "test_domain.object", {"group.location_group", "test_domain.object"}
    )
    assert info.rate_limit is None


async def test_closest_function_home_vs_group_state(hass: HomeAssistant) -> None:
    """Test closest function home vs group state."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_in_group.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "location group",
        created_by_service=False,
        entity_ids=["test_domain.object"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, "test_domain.object", {"group.location_group", "test_domain.object"}
    )
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ closest(states.group.location_group).entity_id }}")
    assert_result_info(
        info, "test_domain.object", {"test_domain.object", "group.location_group"}
    )
    assert info.rate_limit is None


async def test_expand(hass: HomeAssistant) -> None:
    """Test expand function."""
    info = render_to_info(hass, "{{ expand('test.object') }}")
    assert_result_info(info, [], ["test.object"])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ expand(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    hass.states.async_set("test.object", "happy")

    info = render_to_info(
        hass,
        "{{ expand('test.object') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", ["test.object"])
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand('group.new_group') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "", ["group.new_group"])
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand(states.group) | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "", [], ["group"])
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "new group",
        created_by_service=False,
        entity_ids=["test.object"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(
        hass,
        "{{ expand('group.new_group') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"group.new_group", "test.object"})
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand(states.group) | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"test.object"}, ["group"])
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    info = render_to_info(
        hass,
        (
            "{{ expand('group.new_group', 'test.object')"
            " | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(info, "test.object", {"test.object", "group.new_group"})

    info = render_to_info(
        hass,
        (
            "{{ ['group.new_group', 'test.object'] | expand"
            " | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(info, "test.object", {"test.object", "group.new_group"})
    assert info.rate_limit is None

    hass.states.async_set("sensor.power_1", 0)
    hass.states.async_set("sensor.power_2", 200.2)
    hass.states.async_set("sensor.power_3", 400.4)

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "power sensors",
        created_by_service=False,
        entity_ids=["sensor.power_1", "sensor.power_2", "sensor.power_3"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(
        hass,
        (
            "{{ states.group.power_sensors.attributes.entity_id | expand "
            "| sort(attribute='entity_id') | map(attribute='state')|map('float')|sum  }}"
        ),
    )
    assert_result_info(
        info,
        200.2 + 400.4,
        {"group.power_sensors", "sensor.power_1", "sensor.power_2", "sensor.power_3"},
    )
    assert info.rate_limit is None

    # With group entities
    hass.states.async_set("light.first", "on")
    hass.states.async_set("light.second", "off")

    assert await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "group",
                "name": "Grouped",
                "entities": ["light.first", "light.second"],
            }
        },
    )
    await hass.async_block_till_done()

    info = render_to_info(
        hass,
        "{{ expand('light.grouped') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "light.first, light.second",
        ["light.grouped", "light.first", "light.second"],
    )

    assert await async_setup_component(
        hass,
        "zone",
        {
            "zone": {
                "name": "Test",
                "latitude": 32.880837,
                "longitude": -117.237561,
                "radius": 250,
                "passive": False,
            }
        },
    )
    info = render_to_info(
        hass,
        "{{ expand('zone.test') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "",
        ["zone.test"],
    )

    hass.states.async_set(
        "person.person1",
        "test",
    )
    await hass.async_block_till_done()

    info = render_to_info(
        hass,
        "{{ expand('zone.test') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "person.person1",
        ["zone.test", "person.person1"],
    )

    hass.states.async_set(
        "person.person2",
        "test",
    )
    await hass.async_block_till_done()

    info = render_to_info(
        hass,
        "{{ expand('zone.test') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "person.person1, person.person2",
        ["zone.test", "person.person1", "person.person2"],
    )


async def test_integration_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test integration_entities function."""
    # test entities for untitled config entry
    config_entry = MockConfigEntry(domain="mock", title="")
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor", "mock", "untitled", config_entry=config_entry
    )
    info = render_to_info(hass, "{{ integration_entities('') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # test entities for given config entry title
    config_entry = MockConfigEntry(domain="mock", title="Mock bridge 2")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "mock", "test", config_entry=config_entry
    )
    info = render_to_info(hass, "{{ integration_entities('Mock bridge 2') }}")
    assert_result_info(info, [entity_entry.entity_id])
    assert info.rate_limit is None

    # test entities for given non unique config entry title
    config_entry = MockConfigEntry(domain="mock", title="Not unique")
    config_entry.add_to_hass(hass)
    entity_entry_not_unique_1 = entity_registry.async_get_or_create(
        "sensor", "mock", "not_unique_1", config_entry=config_entry
    )
    config_entry = MockConfigEntry(domain="mock", title="Not unique")
    config_entry.add_to_hass(hass)
    entity_entry_not_unique_2 = entity_registry.async_get_or_create(
        "sensor", "mock", "not_unique_2", config_entry=config_entry
    )
    info = render_to_info(hass, "{{ integration_entities('Not unique') }}")
    assert_result_info(
        info, [entity_entry_not_unique_1.entity_id, entity_entry_not_unique_2.entity_id]
    )
    assert info.rate_limit is None

    # test integration entities not in entity registry
    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "light.test_entity"
    mock_entity.platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="light",
        platform_name="entryless_integration",
        platform=None,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    await mock_entity.async_internal_added_to_hass()
    info = render_to_info(hass, "{{ integration_entities('entryless_integration') }}")
    assert_result_info(info, ["light.test_entity"])
    assert info.rate_limit is None

    # Test non existing integration/entry title
    info = render_to_info(hass, "{{ integration_entities('abc123') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None


async def test_config_entry_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test config_entry_id function."""
    config_entry = MockConfigEntry(domain="light", title="Some integration")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "test", suggested_object_id="test", config_entry=config_entry
    )

    info = render_to_info(hass, "{{ 'sensor.fail' | config_entry_id }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 56 | config_entry_id }}")
    assert_result_info(info, None)

    info = render_to_info(hass, "{{ 'not_a_real_entity_id' | config_entry_id }}")
    assert_result_info(info, None)

    info = render_to_info(
        hass, f"{{{{ config_entry_id('{entity_entry.entity_id}') }}}}"
    )
    assert_result_info(info, config_entry.entry_id)
    assert info.rate_limit is None


async def test_config_entry_attr(hass: HomeAssistant) -> None:
    """Test config entry attr."""
    info = {
        "domain": "mock_light",
        "title": "mock title",
        "source": config_entries.SOURCE_BLUETOOTH,
        "disabled_by": config_entries.ConfigEntryDisabler.USER,
    }
    config_entry = MockConfigEntry(**info)
    config_entry.add_to_hass(hass)

    info["state"] = config_entries.ConfigEntryState.NOT_LOADED

    for key, value in info.items():
        assert render(
            hass,
            "{{ config_entry_attr('" + config_entry.entry_id + "', '" + key + "') }}",
            parse_result=False,
        ) == str(value)

    for config_entry_id, key in (
        (config_entry.entry_id, "invalid_key"),
        (56, "domain"),
    ):
        with pytest.raises(TemplateError):
            render(
                hass,
                "{{ config_entry_attr("
                + json.dumps(config_entry_id)
                + ", '"
                + key
                + "') }}",
            )

    assert (
        render(
            hass, "{{ config_entry_attr('invalid_id', 'domain') }}", parse_result=False
        )
        == "None"
    )


def test_closest_function_to_coord(hass: HomeAssistant) -> None:
    """Test closest function to coord."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    result = render(
        hass,
        f'{{{{ closest("{hass.config.latitude + 0.3}", {hass.config.longitude + 0.3}, states.test_domain).entity_id }}}}',
    )
    assert result == "test_domain.closest_zone"

    result = render(
        hass,
        f'{{{{ (states.test_domain | closest("{hass.config.latitude + 0.3}", {hass.config.longitude + 0.3})).entity_id }}}}',
    )
    assert result == "test_domain.closest_zone"


def test_async_render_to_info_with_branching(hass: HomeAssistant) -> None:
    """Test async_render_to_info function by domain."""
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "on")
    hass.states.async_set("light.c", "off")

    info = render_to_info(
        hass,
        """
{% if states.light.a == "on" %}
  {{ states.light.b.state }}
{% else %}
  {{ states.light.c.state }}
{% endif %}
""",
    )
    assert_result_info(info, "off", {"light.a", "light.c"})
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        """
            {% if states.light.a.state == "off" %}
            {% set domain = "light" %}
            {{ states[domain].b.state }}
            {% endif %}
""",
    )
    assert_result_info(info, "on", {"light.a", "light.b"})
    assert info.rate_limit is None


def test_async_render_to_info_with_complex_branching(hass: HomeAssistant) -> None:
    """Test async_render_to_info function by domain."""
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "on")
    hass.states.async_set("light.c", "off")
    hass.states.async_set("vacuum.a", "off")
    hass.states.async_set("device_tracker.a", "off")
    hass.states.async_set("device_tracker.b", "off")
    hass.states.async_set("lock.a", "off")
    hass.states.async_set("sensor.a", "off")
    hass.states.async_set("binary_sensor.a", "off")

    info = render_to_info(
        hass,
        """
{% set domain = "vacuum" %}
{%      if                 states.light.a == "on" %}
  {{ states.light.b.state }}
{% elif  states.light.a == "on" %}
  {{ states.device_tracker }}
{%     elif     states.light.a == "on" %}
  {{ states[domain] | list }}
{%         elif     states('light.b') == "on" %}
  {{ states[otherdomain] | sort(attribute='entity_id') | map(attribute='entity_id') | list }}
{% elif states.light.a == "on" %}
  {{ states["nonexist"] | list }}
{% else %}
  else
{% endif %}
""",
        {"otherdomain": "sensor"},
    )

    assert_result_info(info, ["sensor.a"], {"light.a", "light.b"}, {"sensor"})
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT


async def test_async_render_to_info_with_wildcard_matching_entity_id(
    hass: HomeAssistant,
) -> None:
    """Test tracking template with a wildcard."""
    template_complex_str = r"""

{% for state in states.cover %}
  {% if 'office_' in state.entity_id %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    hass.states.async_set("cover.office_drapes", "closed")
    hass.states.async_set("cover.office_window", "closed")
    hass.states.async_set("cover.office_skylight", "open")
    info = render_to_info(hass, template_complex_str)

    assert info.domains == {"cover"}
    assert info.entities == set()
    assert info.all_states is False
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT


async def test_async_render_to_info_with_wildcard_matching_state(
    hass: HomeAssistant,
) -> None:
    """Test tracking template with a wildcard."""
    template_complex_str = """

{% for state in states %}
  {% if state.state.startswith('ope') %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    hass.states.async_set("cover.office_drapes", "closed")
    hass.states.async_set("cover.office_window", "closed")
    hass.states.async_set("cover.office_skylight", "open")
    hass.states.async_set("cover.x_skylight", "open")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    info = render_to_info(hass, template_complex_str)

    assert not info.domains
    assert info.entities == set()
    assert info.all_states is True
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    hass.states.async_set("binary_sensor.door", "off")
    info = render_to_info(hass, template_complex_str)

    assert not info.domains
    assert info.entities == set()
    assert info.all_states is True
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    template_cover_str = """

{% for state in states.cover %}
  {% if state.state.startswith('ope') %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    hass.states.async_set("cover.x_skylight", "closed")
    info = render_to_info(hass, template_cover_str)

    assert info.domains == {"cover"}
    assert info.entities == set()
    assert info.all_states is False
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT


def test_nested_async_render_to_info_case(hass: HomeAssistant) -> None:
    """Test a deeply nested state with async_render_to_info."""

    hass.states.async_set("input_select.picker", "vacuum.a")
    hass.states.async_set("vacuum.a", "off")

    info = render_to_info(
        hass, "{{ states[states['input_select.picker'].state].state }}", {}
    )
    assert_result_info(info, "off", {"input_select.picker", "vacuum.a"})
    assert info.rate_limit is None


def test_result_as_boolean(hass: HomeAssistant) -> None:
    """Test converting a template result to a boolean."""

    assert template.result_as_boolean(True) is True
    assert template.result_as_boolean(" 1 ") is True
    assert template.result_as_boolean(" true ") is True
    assert template.result_as_boolean(" TrUE ") is True
    assert template.result_as_boolean(" YeS ") is True
    assert template.result_as_boolean(" On ") is True
    assert template.result_as_boolean(" Enable ") is True
    assert template.result_as_boolean(1) is True
    assert template.result_as_boolean(-1) is True
    assert template.result_as_boolean(500) is True
    assert template.result_as_boolean(0.5) is True
    assert template.result_as_boolean(0.389) is True
    assert template.result_as_boolean(35) is True

    assert template.result_as_boolean(False) is False
    assert template.result_as_boolean(" 0 ") is False
    assert template.result_as_boolean(" false ") is False
    assert template.result_as_boolean(" FaLsE ") is False
    assert template.result_as_boolean(" no ") is False
    assert template.result_as_boolean(" off ") is False
    assert template.result_as_boolean(" disable ") is False
    assert template.result_as_boolean(0) is False
    assert template.result_as_boolean(0.0) is False
    assert template.result_as_boolean("0.00") is False
    assert template.result_as_boolean(None) is False


def test_closest_function_to_entity_id(hass: HomeAssistant) -> None:
    """Test closest function to entity id."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    info = render_to_info(
        hass,
        "{{ closest(zone, states.test_domain).entity_id }}",
        {"zone": "zone.far_away"},
    )

    assert_result_info(
        info,
        "test_domain.closest_zone",
        ["test_domain.closest_home", "test_domain.closest_zone", "zone.far_away"],
        ["test_domain"],
    )

    info = render_to_info(
        hass,
        (
            "{{ ([states.test_domain, 'test_domain.closest_zone'] "
            "| closest(zone)).entity_id }}"
        ),
        {"zone": "zone.far_away"},
    )

    assert_result_info(
        info,
        "test_domain.closest_zone",
        ["test_domain.closest_home", "test_domain.closest_zone", "zone.far_away"],
        ["test_domain"],
    )


def test_closest_function_to_state(hass: HomeAssistant) -> None:
    """Test closest function to state."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    assert (
        render(
            hass, "{{ closest(states.zone.far_away, states.test_domain).entity_id }}"
        )
        == "test_domain.closest_zone"
    )


def test_closest_function_invalid_state(hass: HomeAssistant) -> None:
    """Test closest function invalid state."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    for state in ("states.zone.non_existing", '"zone.non_existing"'):
        assert render(hass, f"{{{{ closest({state}, states) }}}}") is None


def test_closest_function_state_with_invalid_location(hass: HomeAssistant) -> None:
    """Test closest function state with invalid location."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {"latitude": "invalid latitude", "longitude": hass.config.longitude + 0.1},
    )

    assert (
        render(hass, "{{ closest(states.test_domain.closest_home, states) }}") is None
    )


def test_closest_function_invalid_coordinates(hass: HomeAssistant) -> None:
    """Test closest function invalid coordinates."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    assert render(hass, '{{ closest("invalid", "coord", states) }}') is None
    assert render(hass, '{{ states | closest("invalid", "coord") }}') is None


def test_closest_function_no_location_states(hass: HomeAssistant) -> None:
    """Test closest function without location states."""
    assert render(hass, "{{ closest(states).entity_id }}") == ""


def test_generate_filter_iterators(hass: HomeAssistant) -> None:
    """Test extract entities function with none entities stuff."""
    info = render_to_info(
        hass,
        """
        {% for state in states %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "", all_states=True)

    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "", domains=["sensor"])

    hass.states.async_set("sensor.test_sensor", "off", {"attr": "value"})

    # Don't need the entity because the state is not accessed
    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor", domains=["sensor"])

    # But we do here because the state gets accessed
    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.state }},
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor=off,", [], ["sensor"])

    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.attributes.attr }},
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor=value,", [], ["sensor"])


def test_generate_select(hass: HomeAssistant) -> None:
    """Test extract entities function with none entities stuff."""
    template_str = """
{{ states.sensor|selectattr("state","equalto","off")
|join(",", attribute="entity_id") }}
        """

    info = render_to_info(hass, template_str)
    assert_result_info(info, "", [], [])
    assert info.domains_lifecycle == {"sensor"}

    hass.states.async_set("sensor.test_sensor", "off", {"attr": "value"})
    hass.states.async_set("sensor.test_sensor_on", "on")

    info = render_to_info(hass, template_str)
    assert_result_info(
        info,
        "sensor.test_sensor",
        [],
        ["sensor"],
    )
    assert info.domains_lifecycle == {"sensor"}


async def test_async_render_to_info_in_conditional(hass: HomeAssistant) -> None:
    """Test extract entities function with none entities stuff."""
    info = render_to_info(hass, '{{ states("sensor.xyz") == "dog" }}')
    assert_result_info(info, False, ["sensor.xyz"], [])

    hass.states.async_set("sensor.xyz", "dog")
    hass.states.async_set("sensor.cow", "True")
    await hass.async_block_till_done()

    template_str = """
{% if states("sensor.xyz") == "dog" %}
  {{ states("sensor.cow") }}
{% else %}
  {{ states("sensor.pig") }}
{% endif %}
        """

    info = render_to_info(hass, template_str)
    assert_result_info(info, True, ["sensor.xyz", "sensor.cow"], [])

    hass.states.async_set("sensor.xyz", "sheep")
    hass.states.async_set("sensor.pig", "oink")

    await hass.async_block_till_done()

    info = render_to_info(hass, template_str)
    assert_result_info(info, "oink", ["sensor.xyz", "sensor.pig"], [])


def test_jinja_namespace(hass: HomeAssistant) -> None:
    """Test Jinja's namespace command can be used."""
    test_template = template.Template(
        (
            "{% set ns = namespace(a_key='') %}"
            "{% set ns.a_key = states.sensor.dummy.state %}"
            "{{ ns.a_key }}"
        ),
        hass,
    )

    hass.states.async_set("sensor.dummy", "a value")
    assert test_template.async_render() == "a value"

    hass.states.async_set("sensor.dummy", "another value")
    assert test_template.async_render() == "another value"


def test_state_with_unit(hass: HomeAssistant) -> None:
    """Test the state_with_unit property helper."""
    hass.states.async_set("sensor.test", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "wow")

    result = render(hass, "{{ states.sensor.test.state_with_unit }}")
    assert result == "23 beers"

    result = render(hass, "{{ states.sensor.test2.state_with_unit }}")
    assert result == "wow"

    result = render(
        hass, "{% for state in states %}{{ state.state_with_unit }} {% endfor %}"
    )
    assert result == "23 beers wow"

    result = render(hass, "{{ states.sensor.non_existing.state_with_unit }}")
    assert result == ""


def test_state_with_unit_and_rounding(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test formatting the state rounded and with unit."""
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "very_unique", suggested_object_id="test"
    )
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor",
        {
            "suggested_display_precision": 2,
        },
    )
    assert entry.entity_id == "sensor.test"

    hass.states.async_set("sensor.test", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test3", "-0.0", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test4", "-0", {ATTR_UNIT_OF_MEASUREMENT: "beers"})

    # state_with_unit property
    tpl = template.Template("{{ states.sensor.test.state_with_unit }}", hass)
    tpl2 = template.Template("{{ states.sensor.test2.state_with_unit }}", hass)

    # AllStates.__call__ defaults
    tpl3 = template.Template("{{ states('sensor.test') }}", hass)
    tpl4 = template.Template("{{ states('sensor.test2') }}", hass)

    # AllStates.__call__ and with_unit=True
    tpl5 = template.Template("{{ states('sensor.test', with_unit=True) }}", hass)
    tpl6 = template.Template("{{ states('sensor.test2', with_unit=True) }}", hass)

    # AllStates.__call__ and rounded=True
    tpl7 = template.Template("{{ states('sensor.test', rounded=True) }}", hass)
    tpl8 = template.Template("{{ states('sensor.test2', rounded=True) }}", hass)
    tpl9 = template.Template("{{ states('sensor.test3', rounded=True) }}", hass)
    tpl10 = template.Template("{{ states('sensor.test4', rounded=True) }}", hass)

    assert tpl.async_render() == "23.00 beers"
    assert tpl2.async_render() == "23 beers"
    assert tpl3.async_render() == 23
    assert tpl4.async_render() == 23
    assert tpl5.async_render() == "23.00 beers"
    assert tpl6.async_render() == "23 beers"
    assert tpl7.async_render() == 23.0
    assert tpl8.async_render() == 23
    assert tpl9.async_render() == 0.0
    assert tpl10.async_render() == 0

    hass.states.async_set("sensor.test", "23.015", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "23.015", {ATTR_UNIT_OF_MEASUREMENT: "beers"})

    assert tpl.async_render() == "23.02 beers"
    assert tpl2.async_render() == "23.015 beers"
    assert tpl3.async_render() == 23.015
    assert tpl4.async_render() == 23.015
    assert tpl5.async_render() == "23.02 beers"
    assert tpl6.async_render() == "23.015 beers"
    assert tpl7.async_render() == 23.02
    assert tpl8.async_render() == 23.015


@pytest.mark.parametrize(
    ("rounded", "with_unit", "output1_1", "output1_2", "output2_1", "output2_2"),
    [
        (False, False, 23, 23.015, 23, 23.015),
        (False, True, "23 beers", "23.015 beers", "23 beers", "23.015 beers"),
        (True, False, 23.0, 23.02, 23, 23.015),
        (True, True, "23.00 beers", "23.02 beers", "23 beers", "23.015 beers"),
    ],
)
def test_state_with_unit_and_rounding_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    rounded: str,
    with_unit: str,
    output1_1,
    output1_2,
    output2_1,
    output2_2,
) -> None:
    """Test formatting the state rounded and with unit."""
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "very_unique", suggested_object_id="test"
    )
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor",
        {
            "suggested_display_precision": 2,
        },
    )
    assert entry.entity_id == "sensor.test"

    hass.states.async_set("sensor.test", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})

    tpl = template.Template(
        f"{{{{ states('sensor.test', rounded={rounded}, with_unit={with_unit}) }}}}",
        hass,
    )
    tpl2 = template.Template(
        f"{{{{ states('sensor.test2', rounded={rounded}, with_unit={with_unit}) }}}}",
        hass,
    )

    assert tpl.async_render() == output1_1
    assert tpl2.async_render() == output2_1

    hass.states.async_set("sensor.test", "23.015", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "23.015", {ATTR_UNIT_OF_MEASUREMENT: "beers"})

    assert tpl.async_render() == output1_2
    assert tpl2.async_render() == output2_2


def test_length_of_states(hass: HomeAssistant) -> None:
    """Test fetching the length of states."""
    hass.states.async_set("sensor.test", "23")
    hass.states.async_set("sensor.test2", "wow")
    hass.states.async_set("climate.test2", "cooling")

    result = render(hass, "{{ states | length }}")
    assert result == 3

    result = render(hass, "{{ states.sensor | length }}")
    assert result == 2


def test_render_complex_handling_non_template_values(hass: HomeAssistant) -> None:
    """Test that we can render non-template fields."""
    assert template.render_complex(
        {True: 1, False: template.Template("{{ hello }}", hass)}, {"hello": 2}
    ) == {True: 1, False: 2}


def test_iif(hass: HomeAssistant) -> None:
    """Test the immediate if function/filter."""

    result = render(hass, "{{ (1 == 1) | iif }}")
    assert result is True

    result = render(hass, "{{ (1 == 2) | iif }}")
    assert result is False

    result = render(hass, "{{ (1 == 1) | iif('yes') }}")
    assert result == "yes"

    result = render(hass, "{{ (1 == 2) | iif('yes') }}")
    assert result is False

    result = render(hass, "{{ (1 == 2) | iif('yes', 'no') }}")
    assert result == "no"

    result = render(hass, "{{ not_exists | default(None) | iif('yes', 'no') }}")
    assert result == "no"

    result = render(
        hass, "{{ not_exists | default(None) | iif('yes', 'no', 'unknown') }}"
    )
    assert result == "unknown"

    result = render(hass, "{{ iif(1 == 1) }}")
    assert result is True

    result = render(hass, "{{ iif(1 == 2, 'yes', 'no') }}")
    assert result == "no"


@pytest.mark.usefixtures("hass")
async def test_cache_garbage_collection() -> None:
    """Test caching a template."""
    template_string = (
        "{% set dict = {'foo': 'x&y', 'bar': 42} %} {{ dict | urlencode }}"
    )
    tpl = template.Template(
        (template_string),
    )
    tpl.ensure_valid()
    assert template._NO_HASS_ENV.template_cache.get(template_string)

    tpl2 = template.Template(
        (template_string),
    )
    tpl2.ensure_valid()
    assert template._NO_HASS_ENV.template_cache.get(template_string)

    del tpl
    assert template._NO_HASS_ENV.template_cache.get(template_string)
    del tpl2
    assert not template._NO_HASS_ENV.template_cache.get(template_string)


def test_is_template_string() -> None:
    """Test is template string."""
    assert template.is_template_string("{{ x }}") is True
    assert template.is_template_string("{% if x == 2 %}1{% else %}0{%end if %}") is True
    assert template.is_template_string("{# a comment #} Hey") is True
    assert template.is_template_string("1") is False
    assert template.is_template_string("Some Text") is False


async def test_protected_blocked(hass: HomeAssistant) -> None:
    """Test accessing __getattr__ produces a template error."""
    with pytest.raises(TemplateError):
        render(hass, '{{ states.__getattr__("any") }}')

    with pytest.raises(TemplateError):
        render(hass, '{{ states.sensor.__getattr__("any") }}')

    with pytest.raises(TemplateError):
        render(hass, '{{ states.sensor.any.__getattr__("any") }}')


async def test_demo_template(hass: HomeAssistant) -> None:
    """Test the demo template works as expected."""
    hass.states.async_set(
        "sun.sun",
        "above",
        {"elevation": 50, "next_rising": "2022-05-12T03:00:08.503651+00:00"},
    )
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "on")

    demo_template_str = """
{## Imitate available variables: ##}
{% set my_test_json = {
  "temperature": 25,
  "unit": "°C"
} %}

The temperature is {{ my_test_json.temperature }} {{ my_test_json.unit }}.

{% if is_state("sun.sun", "above_horizon") -%}
  The sun rose {{ relative_time(states.sun.sun.last_changed) }} ago.
{%- else -%}
  The sun will rise at {{ as_timestamp(state_attr("sun.sun", "next_rising")) | timestamp_local }}.
{%- endif %}

For loop example getting 3 entity values:

{% for states in states | slice(3) -%}
  {% set state = states | first %}
  {%- if loop.first %}The {% elif loop.last %} and the {% else %}, the {% endif -%}
  {{ state.name | lower }} is {{state.state_with_unit}}
{%- endfor %}.
"""
    result = render(hass, demo_template_str)
    assert "The temperature is 25" in result
    assert "is on" in result
    assert "sensor0" in result
    assert "sensor1" in result
    assert "sun" in result


async def test_slice_states(hass: HomeAssistant) -> None:
    """Test iterating states with a slice."""
    hass.states.async_set("sensor.test", "23")

    result = render(
        hass,
        (
            "{% for states in states | slice(1) -%}{% set state = states | first %}"
            "{{ state.entity_id }}"
            "{%- endfor %}"
        ),
    )
    assert result == "sensor.test"


async def test_lifecycle(hass: HomeAssistant) -> None:
    """Test that we limit template render info for lifecycle events."""
    hass.states.async_set("sun.sun", "above", {"elevation": 50, "next_rising": "later"})
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "on")
    hass.states.async_set("sensor.removed", "off")

    await hass.async_block_till_done()

    hass.states.async_set("sun.sun", "below", {"elevation": 60, "next_rising": "later"})
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "off")

    hass.states.async_set("sensor.new", "off")
    hass.states.async_remove("sensor.removed")

    await hass.async_block_till_done()

    info = render_to_info(hass, "{{ states | count }}")
    assert info.all_states is False
    assert info.all_states_lifecycle is True
    assert info.rate_limit is None
    assert info.has_time is False

    assert info.entities == set()
    assert info.domains == set()
    assert info.domains_lifecycle == set()

    assert info.filter("sun.sun") is False
    assert info.filter("sensor.sensor1") is False
    assert info.filter_lifecycle("sensor.new") is True
    assert info.filter_lifecycle("sensor.removed") is True


async def test_template_timeout(hass: HomeAssistant) -> None:
    """Test to see if a template will timeout."""
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "on")

    tmp = template.Template("{{ states | count }}", hass)
    assert await tmp.async_render_will_timeout(3) is False

    tmp3 = template.Template("static", hass)
    assert await tmp3.async_render_will_timeout(3) is False

    tmp4 = template.Template("{{ var1 }}", hass)
    assert await tmp4.async_render_will_timeout(3, {"var1": "ok"}) is False

    slow_template_str = """
{% for var in range(1000) -%}
  {% for var in range(1000) -%}
    {{ var }}
  {%- endfor %}
{%- endfor %}
"""
    tmp5 = template.Template(slow_template_str, hass)
    assert await tmp5.async_render_will_timeout(0.000001) is True


async def test_template_timeout_raise(hass: HomeAssistant) -> None:
    """Test we can raise from."""
    tmp2 = template.Template("{{ error_invalid + 1 }}", hass)
    with pytest.raises(TemplateError):
        assert await tmp2.async_render_will_timeout(3) is False


async def test_lights(hass: HomeAssistant) -> None:
    """Test we can sort lights."""

    tmpl = """
          {% set lights_on = states.light|selectattr('state','eq','on')|sort(attribute='entity_id')|map(attribute='name')|list %}
          {% if lights_on|length == 0 %}
            No lights on. Sleep well..
          {% elif lights_on|length == 1 %}
            The {{lights_on[0]}} light is on.
          {% elif lights_on|length == 2 %}
            The {{lights_on[0]}} and {{lights_on[1]}} lights are on.
          {% else %}
            The {{lights_on[:-1]|join(', ')}}, and {{lights_on[-1]}} lights are on.
          {% endif %}
    """
    states = []
    for i in range(10):
        states.append(f"light.sensor{i}")
        hass.states.async_set(f"light.sensor{i}", "on")

    info = render_to_info(hass, tmpl)
    assert info.entities == set()
    assert info.domains == {"light"}

    assert "lights are on" in info.result()
    for i in range(10):
        assert f"sensor{i}" in info.result()


async def test_template_errors(hass: HomeAssistant) -> None:
    """Test template rendering wraps exceptions with TemplateError."""

    with pytest.raises(TemplateError):
        render(hass, "{{ now() | rando }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ utcnow() | rando }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ now() | random }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ utcnow() | random }}")


async def test_state_attributes(hass: HomeAssistant) -> None:
    """Test state attributes."""
    hass.states.async_set("sensor.test", "23")

    result = render(hass, "{{ states.sensor.test.last_changed }}")
    assert result == str(hass.states.get("sensor.test").last_changed)

    result = render(hass, "{{ states.sensor.test.object_id }}")
    assert result == hass.states.get("sensor.test").object_id

    result = render(hass, "{{ states.sensor.test.domain }}")
    assert result == hass.states.get("sensor.test").domain

    result = render(hass, "{{ states.sensor.test.context.id }}")
    assert result == hass.states.get("sensor.test").context.id

    result = render(hass, "{{ states.sensor.test.state_with_unit }}")
    assert result == 23

    result = render(hass, "{{ states.sensor.test.invalid_prop }}")
    assert result == ""

    with pytest.raises(TemplateError):
        render(hass, "{{ states.sensor.test.invalid_prop.xx }}")


async def test_unavailable_states(hass: HomeAssistant) -> None:
    """Test watching unavailable states."""

    for i in range(10):
        hass.states.async_set(f"light.sensor{i}", "on")

    hass.states.async_set("light.unavailable", "unavailable")
    hass.states.async_set("light.unknown", "unknown")
    hass.states.async_set("light.none", "none")

    result = render(
        hass,
        (
            "{{ states | selectattr('state', 'in', ['unavailable','unknown','none']) "
            "| sort(attribute='entity_id') | map(attribute='entity_id') | list | join(', ') }}"
        ),
    )
    assert result == "light.none, light.unavailable, light.unknown"

    result = render(
        hass,
        (
            "{{ states.light "
            "| selectattr('state', 'in', ['unavailable','unknown','none']) "
            "| sort(attribute='entity_id') | map(attribute='entity_id') | list "
            "| join(', ') }}"
        ),
    )
    assert result == "light.none, light.unavailable, light.unknown"


async def test_no_result_parsing(hass: HomeAssistant) -> None:
    """Test if templates results are not parsed."""
    hass.states.async_set("sensor.temperature", "12")

    assert (
        render(hass, "{{ states.sensor.temperature.state }}", parse_result=False)
        == "12"
    )

    assert render(hass, "{{ false }}", parse_result=False) == "False"

    assert render(hass, "{{ [1, 2, 3] }}", parse_result=False) == "[1, 2, 3]"


async def test_is_static_still_ast_evals(hass: HomeAssistant) -> None:
    """Test is_static still converts to native type."""
    tpl = template.Template("[1, 2]", hass)
    assert tpl.is_static
    assert tpl.async_render() == [1, 2]


async def test_result_wrappers(hass: HomeAssistant) -> None:
    """Test result wrappers."""
    for text, native, orig_type, schema in (
        ("[1, 2]", [1, 2], list, vol.Schema([int])),
        ("{1, 2}", {1, 2}, set, vol.Schema({int})),
        ("(1, 2)", (1, 2), tuple, vol.ExactSequence([int, int])),
        ('{"hello": True}', {"hello": True}, dict, vol.Schema({"hello": bool})),
    ):
        result = render(hass, text)
        assert isinstance(result, orig_type)
        assert isinstance(result, template.ResultWrapper)
        assert result == native
        assert result.render_result == text
        schema(result)  # should not raise
        # Result with render text stringifies to original text
        assert str(result) == text
        # Result without render text stringifies same as original type
        assert str(template.RESULT_WRAPPERS[orig_type](native)) == str(
            orig_type(native)
        )


async def test_parse_result(hass: HomeAssistant) -> None:
    """Test parse result."""
    for tpl, result in (
        ('{{ "{{}}" }}', "{{}}"),
        ("not-something", "not-something"),
        ("2a", "2a"),
        ("123E5", "123E5"),
        ("1j", "1j"),
        ("1e+100", "1e+100"),
        ("0xface", "0xface"),
        ("123", 123),
        ("10", 10),
        ("123.0", 123.0),
        (".5", 0.5),
        ("0.5", 0.5),
        ("-1", -1),
        ("-1.0", -1.0),
        ("+1", 1),
        ("5.", 5.0),
        ("123_123_123", "123_123_123"),
        # ("+48100200300", "+48100200300"),  # phone number
        ("010", "010"),
        ("0011101.00100001010001", "0011101.00100001010001"),
    ):
        assert render(hass, tpl) == result


@pytest.mark.parametrize(
    "template_string",
    [
        "{{ no_such_variable }}",
        "{{ no_such_variable and True }}",
        "{{ no_such_variable | join(', ') }}",
    ],
)
async def test_undefined_symbol_warnings(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    template_string: str,
) -> None:
    """Test a warning is logged on undefined variables."""

    assert render(hass, template_string) == ""
    assert (
        f"Template variable warning: 'no_such_variable' is undefined when rendering '{template_string}'"
        in caplog.text
    )


async def test_template_states_blocks_setitem(hass: HomeAssistant) -> None:
    """Test we cannot setitem on TemplateStates."""
    hass.states.async_set("light.new", STATE_ON)
    state = hass.states.get("light.new")
    template_state = template.TemplateState(hass, state, True)
    with pytest.raises(RuntimeError):
        template_state["any"] = "any"


async def test_template_states_can_serialize(hass: HomeAssistant) -> None:
    """Test TemplateState is serializable."""
    hass.states.async_set("light.new", STATE_ON)
    state = hass.states.get("light.new")
    template_state = template.TemplateState(hass, state, True)
    assert template_state.as_dict() is template_state.as_dict()
    assert json_dumps(template_state) == json_dumps(template_state)


@pytest.mark.parametrize(
    ("seq", "value", "expected"),
    [
        ([0], 0, True),
        ([1], 0, False),
        ([False], 0, True),
        ([True], 0, False),
        ([0], [0], False),
        (["toto", 1], "toto", True),
        (["toto", 1], "tata", False),
        ([], 0, False),
        ([], None, False),
    ],
)
def test_contains(hass: HomeAssistant, seq, value, expected) -> None:
    """Test contains."""
    assert (
        render(hass, "{{ seq | contains(value) }}", {"seq": seq, "value": value})
        == expected
    )
    assert (
        render(hass, "{{ seq is contains(value) }}", {"seq": seq, "value": value})
        == expected
    )


async def test_render_to_info_with_exception(hass: HomeAssistant) -> None:
    """Test info is still available if the template has an exception."""
    hass.states.async_set("test_domain.object", "dog")
    info = render_to_info(hass, '{{ states("test_domain.object") | float }}')
    with pytest.raises(TemplateError, match="no default was specified"):
        info.result()

    assert info.all_states is False
    assert info.entities == {"test_domain.object"}


async def test_lru_increases_with_many_entities(hass: HomeAssistant) -> None:
    """Test that the template internal LRU cache increases with many entities."""
    # We do not actually want to record 4096 entities so we mock the entity count
    mock_entity_count = 16

    assert template.CACHED_TEMPLATE_LRU.get_size() == template.CACHED_TEMPLATE_STATES
    assert (
        template.CACHED_TEMPLATE_NO_COLLECT_LRU.get_size()
        == template.CACHED_TEMPLATE_STATES
    )
    template.CACHED_TEMPLATE_LRU.set_size(8)
    template.CACHED_TEMPLATE_NO_COLLECT_LRU.set_size(8)

    template.async_setup(hass)
    for i in range(mock_entity_count):
        hass.states.async_set(f"sensor.sensor{i}", "on")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    assert template.CACHED_TEMPLATE_LRU.get_size() == int(
        round(mock_entity_count * template.ENTITY_COUNT_GROWTH_FACTOR)
    )
    assert template.CACHED_TEMPLATE_NO_COLLECT_LRU.get_size() == int(
        round(mock_entity_count * template.ENTITY_COUNT_GROWTH_FACTOR)
    )

    await hass.async_stop()

    for i in range(mock_entity_count):
        hass.states.async_set(f"sensor.sensor_add_{i}", "on")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
    await hass.async_block_till_done()

    assert template.CACHED_TEMPLATE_LRU.get_size() == int(
        round(mock_entity_count * template.ENTITY_COUNT_GROWTH_FACTOR)
    )
    assert template.CACHED_TEMPLATE_NO_COLLECT_LRU.get_size() == int(
        round(mock_entity_count * template.ENTITY_COUNT_GROWTH_FACTOR)
    )


async def test_template_thread_safety_checks(hass: HomeAssistant) -> None:
    """Test template thread safety checks."""
    hass.states.async_set("sensor.test", "23")
    template_str = "{{ states('sensor.test') }}"
    template_obj = template.Template(template_str, None)
    template_obj.hass = hass
    hass.config.debug = True

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls async_render_to_info from a thread.",
    ):
        await hass.async_add_executor_job(template_obj.async_render_to_info)

    assert template_obj.async_render_to_info().result() == 23


def test_template_output_exceeds_maximum_size(hass: HomeAssistant) -> None:
    """Test template output exceeds maximum size."""
    with pytest.raises(TemplateError):
        render(hass, "{{ 'a' * 1024 * 257 }}")


@pytest.mark.parametrize(
    ("service_response"),
    [
        {
            "calendar.sports": {
                "events": [
                    {
                        "start": "2024-02-27T17:00:00-06:00",
                        "end": "2024-02-27T18:00:00-06:00",
                        "summary": "Basketball vs. Rockets",
                        "description": "",
                    }
                ]
            },
            "calendar.local_furry_events": {"events": []},
            "calendar.yap_house_schedules": {
                "events": [
                    {
                        "start": "2024-02-26T08:00:00-06:00",
                        "end": "2024-02-26T09:00:00-06:00",
                        "summary": "Dr. Appt",
                        "description": "",
                    },
                    {
                        "start": "2024-02-28T20:00:00-06:00",
                        "end": "2024-02-28T21:00:00-06:00",
                        "summary": "Bake a cake",
                        "description": "something good",
                    },
                ]
            },
        },
        {
            "binary_sensor.workday": {"workday": True},
            "binary_sensor.workday2": {"workday": False},
        },
        {
            "weather.smhi_home": {
                "forecast": [
                    {
                        "datetime": "2024-03-31T16:00:00",
                        "condition": "cloudy",
                        "wind_bearing": 79,
                        "cloud_coverage": 100,
                        "temperature": 10,
                        "templow": 4,
                        "pressure": 998,
                        "wind_gust_speed": 21.6,
                        "wind_speed": 11.88,
                        "precipitation": 0.2,
                        "humidity": 87,
                    },
                    {
                        "datetime": "2024-04-01T12:00:00",
                        "condition": "rainy",
                        "wind_bearing": 17,
                        "cloud_coverage": 100,
                        "temperature": 6,
                        "templow": 1,
                        "pressure": 999,
                        "wind_gust_speed": 20.52,
                        "wind_speed": 8.64,
                        "precipitation": 2.2,
                        "humidity": 88,
                    },
                    {
                        "datetime": "2024-04-02T12:00:00",
                        "condition": "cloudy",
                        "wind_bearing": 17,
                        "cloud_coverage": 100,
                        "temperature": 0,
                        "templow": -3,
                        "pressure": 1003,
                        "wind_gust_speed": 57.24,
                        "wind_speed": 30.6,
                        "precipitation": 1.3,
                        "humidity": 71,
                    },
                ]
            },
            "weather.forecast_home": {
                "forecast": [
                    {
                        "condition": "cloudy",
                        "precipitation_probability": 6.6,
                        "datetime": "2024-03-31T10:00:00+00:00",
                        "wind_bearing": 71.8,
                        "temperature": 10.9,
                        "templow": 6.5,
                        "wind_gust_speed": 24.1,
                        "wind_speed": 13.7,
                        "precipitation": 0,
                        "humidity": 71,
                    },
                    {
                        "condition": "cloudy",
                        "precipitation_probability": 8,
                        "datetime": "2024-04-01T10:00:00+00:00",
                        "wind_bearing": 350.6,
                        "temperature": 10.2,
                        "templow": 3.4,
                        "wind_gust_speed": 38.2,
                        "wind_speed": 21.6,
                        "precipitation": 0,
                        "humidity": 79,
                    },
                    {
                        "condition": "snowy",
                        "precipitation_probability": 67.4,
                        "datetime": "2024-04-02T10:00:00+00:00",
                        "wind_bearing": 24.5,
                        "temperature": 3,
                        "templow": 0,
                        "wind_gust_speed": 64.8,
                        "wind_speed": 37.4,
                        "precipitation": 2.3,
                        "humidity": 77,
                    },
                ]
            },
        },
        {
            "vacuum.deebot_n8_plus_1": {
                "payloadType": "j",
                "resp": {
                    "body": {
                        "msg": "ok",
                    }
                },
                "header": {
                    "ver": "0.0.1",
                },
            },
            "vacuum.deebot_n8_plus_2": {
                "payloadType": "j",
                "resp": {
                    "body": {
                        "msg": "ok",
                    }
                },
                "header": {
                    "ver": "0.0.1",
                },
            },
        },
    ],
    ids=["calendar", "workday", "weather", "vacuum"],
)
async def test_merge_response(
    hass: HomeAssistant,
    service_response: dict,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the merge_response function/filter."""

    _template = "{{ merge_response(" + str(service_response) + ") }}"

    assert service_response == snapshot(name="a_response")
    assert render(
        hass,
        _template,
    ) == snapshot(name="b_rendered")


async def test_merge_response_with_entity_id_in_response(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the merge_response function/filter with empty lists."""

    service_response = {
        "test.response": {"some_key": True, "entity_id": "test.response"},
        "test.response2": {"some_key": False, "entity_id": "test.response2"},
    }
    _template = "{{ merge_response(" + str(service_response) + ") }}"
    with pytest.raises(
        TemplateError,
        match="ValueError: Response dictionary already contains key 'entity_id'",
    ):
        render(hass, _template)

    service_response = {
        "test.response": {
            "happening": [
                {
                    "start": "2024-02-27T17:00:00-06:00",
                    "end": "2024-02-27T18:00:00-06:00",
                    "summary": "Magic day",
                    "entity_id": "test.response",
                }
            ]
        }
    }
    _template = "{{ merge_response(" + str(service_response) + ") }}"
    with pytest.raises(
        TemplateError,
        match="ValueError: Response dictionary already contains key 'entity_id'",
    ):
        render(hass, _template)


async def test_merge_response_with_empty_response(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the merge_response function/filter with empty lists."""

    service_response = {
        "calendar.sports": {"events": []},
        "calendar.local_furry_events": {"events": []},
        "calendar.yap_house_schedules": {"events": []},
    }
    _template = "{{ merge_response(" + str(service_response) + ") }}"
    assert service_response == snapshot(name="a_response")
    assert render(hass, _template) == snapshot(name="b_rendered")


async def test_response_empty_dict(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the merge_response function/filter with empty dict."""

    service_response = {}
    _template = "{{ merge_response(" + str(service_response) + ") }}"

    result = render(hass, _template)
    assert result == []


async def test_response_incorrect_value(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the merge_response function/filter with incorrect response."""

    service_response = "incorrect"
    _template = "{{ merge_response(" + str(service_response) + ") }}"
    with pytest.raises(TemplateError, match="TypeError: Response is not a dictionary"):
        render(hass, _template)


async def test_merge_response_with_incorrect_response(hass: HomeAssistant) -> None:
    """Test the merge_response function/filter with empty response should raise."""

    service_response = {"calendar.sports": []}
    _template = "{{ merge_response(" + str(service_response) + ") }}"
    with pytest.raises(TemplateError, match="TypeError: Response is not a dictionary"):
        render(hass, _template)

    service_response = {
        "binary_sensor.workday": [],
    }
    _template = "{{ merge_response(" + str(service_response) + ") }}"
    with pytest.raises(TemplateError, match="TypeError: Response is not a dictionary"):
        render(hass, _template)


def test_warn_no_hass(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecation warning when instantiating Template without hass."""

    message = "Detected code that creates a template object without passing hass"
    template.Template("blah")
    assert message in caplog.text
    caplog.clear()

    template.Template("blah", None)
    assert message in caplog.text
    caplog.clear()

    template.Template("blah", hass)
    assert message not in caplog.text
    caplog.clear()


async def test_merge_response_not_mutate_original_object(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the merge_response does not mutate original service response value."""

    value = '{"calendar.family": {"events": [{"summary": "An event"}]}'
    _template = (
        "{% set calendar_response = " + value + "} %}"
        "{{ merge_response(calendar_response) }}"
        # We should be able to merge the same response again
        # as the merge is working on a copy of the original object (response)
        "{{ merge_response(calendar_response) }}"
    )

    assert render(hass, _template)


def test_typeof(hass: HomeAssistant) -> None:
    """Test the typeof debug filter/function."""
    assert render(hass, "{{ True | typeof }}") == "bool"
    assert render(hass, "{{ typeof(True) }}") == "bool"

    assert render(hass, "{{ [1, 2, 3] | typeof }}") == "list"
    assert render(hass, "{{ typeof([1, 2, 3]) }}") == "list"

    assert render(hass, "{{ 1 | typeof }}") == "int"
    assert render(hass, "{{ typeof(1) }}") == "int"

    assert render(hass, "{{ 1.1 | typeof }}") == "float"
    assert render(hass, "{{ typeof(1.1) }}") == "float"

    assert render(hass, "{{ None | typeof }}") == "NoneType"
    assert render(hass, "{{ typeof(None) }}") == "NoneType"

    assert render(hass, "{{ 'Home Assistant' | typeof }}") == "str"
    assert render(hass, "{{ typeof('Home Assistant') }}") == "str"


def test_combine(hass: HomeAssistant) -> None:
    """Test combine filter and function."""
    assert render(hass, "{{ {'a': 1, 'b': 2} | combine({'b': 3, 'c': 4}) }}") == {
        "a": 1,
        "b": 3,
        "c": 4,
    }

    assert render(hass, "{{ combine({'a': 1, 'b': 2}, {'b': 3, 'c': 4}) }}") == {
        "a": 1,
        "b": 3,
        "c": 4,
    }

    assert render(
        hass,
        "{{ combine({'a': 1, 'b': {'x': 1}}, {'b': {'y': 2}, 'c': 4}, recursive=True) }}",
    ) == {"a": 1, "b": {"x": 1, "y": 2}, "c": 4}

    # Test that recursive=False does not merge nested dictionaries
    assert render(
        hass,
        "{{ combine({'a': 1, 'b': {'x': 1}}, {'b': {'y': 2}, 'c': 4}, recursive=False) }}",
    ) == {"a": 1, "b": {"y": 2}, "c": 4}

    # Test that None values are handled correctly in recursive merge
    assert render(
        hass,
        "{{ combine({'a': 1, 'b': none}, {'b': {'y': 2}, 'c': 4}, recursive=True) }}",
    ) == {"a": 1, "b": {"y": 2}, "c": 4}

    with pytest.raises(
        TemplateError, match="combine expected at least 1 argument, got 0"
    ):
        render(hass, "{{ combine() }}")

    with pytest.raises(TemplateError, match="combine expected a dict, got str"):
        render(hass, "{{ {'a': 1} | combine('not a dict') }}")
