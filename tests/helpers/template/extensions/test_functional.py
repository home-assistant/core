"""Test functional utility functions for Home Assistant templates."""

from __future__ import annotations

import random
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template

from tests.helpers.template.helpers import render


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


def test_ord(hass: HomeAssistant) -> None:
    """Test the ord filter."""
    assert render(hass, '{{ "d" | ord }}') == 100


@patch.object(random, "choice")
def test_random_every_time(test_choice: MagicMock, hass: HomeAssistant) -> None:
    """Ensure the random filter runs every time, not just once."""
    tpl = template.Template("{{ [1,2] | random }}", hass)
    test_choice.return_value = "foo"
    assert tpl.async_render() == "foo"
    test_choice.return_value = "bar"
    assert tpl.async_render() == "bar"


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
def test_contains(
    hass: HomeAssistant, seq: list, value: object, expected: bool
) -> None:
    """Test contains."""
    assert (
        render(hass, "{{ seq | contains(value) }}", {"seq": seq, "value": value})
        == expected
    )
    assert (
        render(hass, "{{ seq is contains(value) }}", {"seq": seq, "value": value})
        == expected
    )


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
