"""Test config validators."""

from collections import OrderedDict
from collections.abc import Callable
from datetime import date, timedelta
import enum
from functools import partial
import logging
import math
import os
from pathlib import Path
import re
from socket import _GLOBAL_DEFAULT_TIMEOUT
import threading
from typing import Any
from unittest.mock import ANY, Mock, patch
import uuid

import probatio
import py
import pytest

import homeassistant
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    selector,
    template,
)
from homeassistant.helpers.config_validation import TRIGGER_SCHEMA
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict


def test_boolean() -> None:
    """Test boolean validation."""
    schema = probatio.Schema(cv.boolean)

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
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("true", "On", "1", "YES", "   true  ", "enable", 1, 50, True, 0.1):
        assert schema(value)

    for value in ("false", "Off", "0", "NO", "disable", 0, False):
        assert not schema(value)


def test_latitude() -> None:
    """Test latitude validation."""
    schema = probatio.Schema(cv.latitude)

    for value in ("invalid", None, -91, 91, "-91", "91", "123.01A"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("-89", 89, "12.34"):
        schema(value)


def test_longitude() -> None:
    """Test longitude validation."""
    schema = probatio.Schema(cv.longitude)

    for value in ("invalid", None, -181, 181, "-181", "181", "123.01A"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("-179", 179, "12.34"):
        schema(value)


def test_port() -> None:
    """Test TCP/UDP network port."""
    schema = probatio.Schema(cv.port)

    for value in ("invalid", None, -1, 0, 80000, "81000"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("1000", 21, 24574):
        schema(value)


def test_isfile() -> None:
    """Validate that the value is an existing file."""
    schema = probatio.Schema(cv.isfile)

    fake_file = "this-file-does-not.exist"
    assert not os.path.isfile(fake_file)

    for value in ("invalid", None, -1, 0, 80000, fake_file):
        with pytest.raises(probatio.Invalid):
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
    schema = probatio.Schema(cv.url)

    for value in (
        "invalid",
        None,
        100,
        "htp://ha.io",
        "http//ha.io",
        "http://??,**",
        "https://??,**",
    ):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in (
        "http://localhost",
        "https://localhost/test/index.html",
        "http://home-assistant.io",
        "http://home-assistant.io/test/",
        "https://community.home-assistant.io/",
    ):
        assert schema(value)


@pytest.mark.parametrize(
    "validator",
    [
        pytest.param(cv.url, id="url"),
        pytest.param(cv.url_no_path, id="url_no_path"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("http://exa mple.com", id="space_in_host"),
        pytest.param("http://user:pass@exa mple.com", id="space_in_host_with_userinfo"),
        pytest.param("http://example.com\x00", id="nul"),
        pytest.param("http://exam\tple.com", id="tab_in_host"),
        pytest.param("http://exam\nple.com", id="newline_in_host"),
        pytest.param("http://exam\u00a0ple.com", id="no_break_space_in_host"),
        pytest.param("http://example.com/pa\tth", id="tab_in_path"),
        pytest.param("http://example.com/?q=a\nb", id="newline_in_query"),
        pytest.param("http://example.com/\x7f", id="delete_in_path"),
    ],
)
def test_url_rejects_whitespace_and_control_chars(
    validator: Callable[[Any], Any], value: str
) -> None:
    """Test URLs containing whitespace or control characters are rejected."""
    with pytest.raises(probatio.Invalid):
        probatio.Schema(validator)(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("\nhttp://example.com", id="leading_newline"),
        pytest.param("http://example.com\n", id="trailing_newline"),
        pytest.param("  http://example.com  ", id="surrounding_spaces"),
    ],
)
def test_url_strips_surrounding_whitespace(value: str) -> None:
    """Test surrounding whitespace is stripped from URLs."""
    assert probatio.Schema(cv.url)(value) == "http://example.com"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("http://example.com/snapshot image.jpg", id="space_in_path"),
        pytest.param(
            "http://example.com/?file=snapshot image.jpg", id="space_in_query"
        ),
        pytest.param("http://example.com/#snapshot image", id="space_in_fragment"),
        pytest.param("http://user:pa ss@example.com/", id="space_in_password"),
        pytest.param("http://us er@example.com/", id="space_in_username"),
    ],
)
def test_url_allows_spaces_outside_host(value: str) -> None:
    """Test spaces outside the host are kept, since HTTP clients encode them."""
    assert probatio.Schema(cv.url)(value) == value


def test_configuration_url() -> None:
    """Test URL."""
    schema = probatio.Schema(cv.configuration_url)

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
        with pytest.raises(probatio.MultipleInvalid):
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
    schema = probatio.Schema(cv.url_no_path)

    for value in (
        "https://localhost/test/index.html",
        "http://home-assistant.io/test/",
        "http://invalid-port.local:999999",
    ):
        with pytest.raises(probatio.MultipleInvalid):
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
        with pytest.raises(probatio.MultipleInvalid):
            cv.PLATFORM_SCHEMA(value)

    options = ({"platform": "mqtt"}, {"platform": "mqtt", "beer": "yes"})
    for value in options:
        cv.PLATFORM_SCHEMA_BASE(value)


def test_ensure_list() -> None:
    """Test ensure_list."""
    schema = probatio.Schema(cv.ensure_list)
    assert schema(None) == []
    assert schema(1) == [1]
    assert schema([1]) == [1]
    assert schema("1") == ["1"]
    assert schema(["1"]) == ["1"]
    assert schema({"1": "2"}) == [{"1": "2"}]


def _even_as_str(value: Any) -> str:
    """Validate an even number and return it as a string."""
    if not isinstance(value, int) or value % 2:
        raise probatio.Invalid("not even")
    return str(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, [], id="none"),
        pytest.param([], [], id="empty_list"),
        pytest.param([2, 4], ["2", "4"], id="list"),
        pytest.param([2], ["2"], id="list_of_one"),
        pytest.param(2, ["2"], id="single"),
        pytest.param(0, ["0"], id="falsy_single"),
    ],
)
def test_list_of(value: Any, expected: list[str]) -> None:
    """Test _list_of gives the same result as All(ensure_list, [validator])."""
    assert cv._list_of(_even_as_str)(value) == expected
    assert probatio.All(cv.ensure_list, [_even_as_str])(value) == expected


@pytest.mark.parametrize(
    ("value", "paths", "ensure_list_paths"),
    [
        pytest.param(3, [[]], [[0]], id="single"),
        pytest.param("2", [[]], [[0]], id="single_str"),
        pytest.param((2,), [[]], [[0]], id="tuple_is_a_single_item"),
        pytest.param([3], [[0]], [[0]], id="list_of_one"),
        pytest.param([2, 3, 4, 5], [[1], [3]], [[1], [3]], id="list"),
    ],
)
def test_list_of_invalid(
    value: Any, paths: list[list[int]], ensure_list_paths: list[list[int]]
) -> None:
    """Test _list_of only adds an index to the error path of a list item."""
    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        cv._list_of(_even_as_str)(value)
    assert [err.path for err in exc_info.value.errors] == paths
    assert [err.msg for err in exc_info.value.errors] == ["not even"] * len(paths)

    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        probatio.All(cv.ensure_list, [_even_as_str])(value)
    assert [err.path for err in exc_info.value.errors] == ensure_list_paths


_VALID_CONDITION = {"condition": "state", "entity_id": "light.kitchen", "state": "on"}
_INVALID_CONDITION = {"condition": "state", "entity_id": "light.kitchen"}
_VALID_ACTION = {"delay": 1}
_INVALID_ACTION = {"delay": "invalid"}
_INVALID_TRIGGER = {"trigger": "event", "alias": 5}


@pytest.mark.parametrize(
    ("schema", "single", "single_path", "as_list", "list_path"),
    [
        pytest.param(
            cv.SCRIPT_SCHEMA,
            _INVALID_ACTION,
            ["delay"],
            [_VALID_ACTION, _INVALID_ACTION],
            [1, "delay"],
            id="script",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            _INVALID_CONDITION,
            ["state"],
            [_VALID_CONDITION, _INVALID_CONDITION],
            [1, "state"],
            id="conditions",
        ),
        pytest.param(
            cv.TRIGGER_SCHEMA,
            _INVALID_TRIGGER,
            ["alias"],
            [{"trigger": "event"}, _INVALID_TRIGGER],
            [1, "alias"],
            id="triggers",
        ),
        pytest.param(
            cv.AND_CONDITION_SCHEMA,
            {"condition": "and", "conditions": _INVALID_CONDITION},
            ["conditions", "state"],
            {"condition": "and", "conditions": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["conditions", 1, "state"],
            id="and",
        ),
        pytest.param(
            cv.OR_CONDITION_SCHEMA,
            {"condition": "or", "conditions": _INVALID_CONDITION},
            ["conditions", "state"],
            {"condition": "or", "conditions": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["conditions", 1, "state"],
            id="or",
        ),
        pytest.param(
            cv.NOT_CONDITION_SCHEMA,
            {"condition": "not", "conditions": _INVALID_CONDITION},
            ["conditions", "state"],
            {"condition": "not", "conditions": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["conditions", 1, "state"],
            id="not",
        ),
        pytest.param(
            cv.AND_CONDITION_SHORTHAND_SCHEMA,
            {"and": _INVALID_CONDITION},
            ["and", "state"],
            {"and": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["and", 1, "state"],
            id="and_shorthand",
        ),
        pytest.param(
            cv.OR_CONDITION_SHORTHAND_SCHEMA,
            {"or": _INVALID_CONDITION},
            ["or", "state"],
            {"or": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["or", 1, "state"],
            id="or_shorthand",
        ),
        pytest.param(
            cv.NOT_CONDITION_SHORTHAND_SCHEMA,
            {"not": _INVALID_CONDITION},
            ["not", "state"],
            {"not": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["not", 1, "state"],
            id="not_shorthand",
        ),
        pytest.param(
            cv.CONDITION_SHORTHAND_SCHEMA,
            {"condition": _INVALID_CONDITION},
            ["condition", "state"],
            {"condition": [_VALID_CONDITION, _INVALID_CONDITION]},
            ["condition", 1, "state"],
            id="condition_shorthand",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"choose": {"conditions": [], "sequence": [], "invalid": 1}},
            ["choose", "invalid"],
            {
                "choose": [
                    {"conditions": [], "sequence": []},
                    {"conditions": [], "sequence": [], "invalid": 1},
                ]
            },
            ["choose", 1, "invalid"],
            id="choose",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"choose": {"conditions": _INVALID_CONDITION, "sequence": []}},
            ["choose", "conditions", "state"],
            {
                "choose": [
                    {"conditions": [], "sequence": []},
                    {
                        "conditions": [_VALID_CONDITION, _INVALID_CONDITION],
                        "sequence": [],
                    },
                ]
            },
            ["choose", 1, "conditions", 1, "state"],
            id="choose_conditions",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"choose": [], "default": _INVALID_ACTION},
            ["default", "delay"],
            {"choose": [], "default": [_VALID_ACTION, _INVALID_ACTION]},
            ["default", 1, "delay"],
            id="choose_default",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"if": _INVALID_CONDITION, "then": []},
            ["if", "state"],
            {"if": [_VALID_CONDITION, _INVALID_CONDITION], "then": []},
            ["if", 1, "state"],
            id="if",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"if": [], "then": [], "else": _INVALID_ACTION},
            ["else", "delay"],
            {"if": [], "then": [], "else": [_VALID_ACTION, _INVALID_ACTION]},
            ["else", 1, "delay"],
            id="else",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"repeat": {"until": _INVALID_CONDITION, "sequence": []}},
            ["repeat", "until", "state"],
            {
                "repeat": {
                    "until": [_VALID_CONDITION, _INVALID_CONDITION],
                    "sequence": [],
                }
            },
            ["repeat", "until", 1, "state"],
            id="repeat_until",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"sequence": _INVALID_ACTION},
            ["sequence", "delay"],
            {"sequence": [_VALID_ACTION, _INVALID_ACTION]},
            ["sequence", 1, "delay"],
            id="sequence",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {"wait_for_trigger": _INVALID_TRIGGER},
            ["wait_for_trigger", "alias"],
            {"wait_for_trigger": [{"trigger": "event"}, _INVALID_TRIGGER]},
            ["wait_for_trigger", 1, "alias"],
            id="wait_for_trigger",
        ),
    ],
)
def test_single_item_error_path(
    schema: Callable[[Any], Any],
    single: Any,
    single_path: list[str | int],
    as_list: Any,
    list_path: list[str | int],
) -> None:
    """Test the error path of an item written without a list has no index."""
    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        schema(single)
    assert [err.path for err in exc_info.value.errors] == [single_path]

    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        schema(as_list)
    assert [err.path for err in exc_info.value.errors] == [list_path]


# These validate to themselves
_UNCHANGED_ACTION = {"event": "test"}
_UNCHANGED_CONDITION = {"condition": "sun"}


@pytest.mark.parametrize(
    ("schema", "single", "expected"),
    [
        pytest.param(
            cv.SCRIPT_SCHEMA, _UNCHANGED_ACTION, [_UNCHANGED_ACTION], id="script"
        ),
        pytest.param(cv.SCRIPT_SCHEMA, None, [], id="script_none"),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            _UNCHANGED_CONDITION,
            [_UNCHANGED_CONDITION],
            id="conditions",
        ),
        pytest.param(cv.CONDITIONS_SCHEMA, None, [], id="conditions_none"),
        pytest.param(
            cv.TRIGGER_SCHEMA,
            {"trigger": "event"},
            [{"platform": "event"}],
            id="triggers",
        ),
        pytest.param(cv.TRIGGER_SCHEMA, None, [], id="triggers_none"),
        pytest.param(
            cv.TRIGGER_SCHEMA,
            {"triggers": {"trigger": "event"}},
            [{"platform": "event"}],
            id="triggers_single_sublist",
        ),
        pytest.param(
            cv.AND_CONDITION_SCHEMA,
            {"condition": "and", "conditions": _UNCHANGED_CONDITION},
            {"condition": "and", "conditions": [_UNCHANGED_CONDITION]},
            id="and",
        ),
        pytest.param(
            cv.CONDITION_SCHEMA,
            {"or": _UNCHANGED_CONDITION},
            {"condition": "or", "conditions": [_UNCHANGED_CONDITION]},
            id="or_shorthand",
        ),
        pytest.param(
            cv.CONDITION_SHORTHAND_SCHEMA,
            {"condition": None},
            {"condition": []},
            id="condition_shorthand_none",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            {
                "choose": {
                    "conditions": _UNCHANGED_CONDITION,
                    "sequence": _UNCHANGED_ACTION,
                }
            },
            [
                {
                    "choose": [
                        {
                            "conditions": [_UNCHANGED_CONDITION],
                            "sequence": [_UNCHANGED_ACTION],
                        }
                    ]
                }
            ],
            id="choose",
        ),
    ],
)
def test_single_item_is_wrapped_in_list(
    schema: Callable[[Any], Any], single: Any, expected: Any
) -> None:
    """Test an item written without a list validates to a list."""
    assert schema(single) == expected


def test_single_trigger_not_a_mapping() -> None:
    """Test a single trigger which is not a mapping is invalid."""
    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        cv.TRIGGER_SCHEMA(5)
    assert [(err.path, err.msg) for err in exc_info.value.errors] == [
        ([], "expected a mapping")
    ]


def test_entity_id() -> None:
    """Test entity ID validation."""
    schema = probatio.Schema(cv.entity_id)

    with pytest.raises(probatio.MultipleInvalid):
        schema("invalid_entity")

    with pytest.raises(probatio.MultipleInvalid):
        schema("sensor.light\n")

    assert schema("sensor.LIGHT") == "sensor.light"


@pytest.mark.parametrize("validator", [cv.entity_ids, cv.entity_ids_or_uuids])
def test_entity_ids(validator) -> None:
    """Test entity ID validation."""
    schema = probatio.Schema(validator)

    options = (
        "invalid_entity",
        "sensor.light,sensor_invalid",
        ["invalid_entity"],
        ["sensor.light", "sensor_invalid"],
        ["sensor.light,sensor_invalid"],
    )
    for value in options:
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    options = ([], ["sensor.light"], "sensor.light")
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, light.kitchen ") == ["sensor.light", "light.kitchen"]


def test_entity_ids_or_uuids() -> None:
    """Test entity ID validation."""
    schema = probatio.Schema(cv.entity_ids_or_uuids)

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
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    options = ([], [valid_uuid], valid_uuid)
    for value in options:
        schema(value)

    assert schema(f"{valid_uuid}, {valid_uuid2} ") == [valid_uuid, valid_uuid2]


def test_entity_domain() -> None:
    """Test entity domain validation."""
    schema = probatio.Schema(cv.entity_domain("sensor"))

    for value in (
        "invalid_entity",
        "cover.demo",
        "cover.demo,sensor.another_entity",
        "",
    ):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    assert schema("sensor.LIGHT") == "sensor.light"

    schema = probatio.Schema(cv.entity_domain(("sensor", "binary_sensor")))

    for value in ("invalid_entity", "cover.demo"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    assert schema("sensor.LIGHT") == "sensor.light"
    assert schema("binary_sensor.LIGHT") == "binary_sensor.light"


@pytest.mark.parametrize(
    "validator",
    [
        pytest.param(cv.entity_ids, id="entity_ids"),
        pytest.param(cv.entity_ids_or_uuids, id="entity_ids_or_uuids"),
        pytest.param(cv.comp_entity_ids, id="comp_entity_ids"),
        pytest.param(cv.comp_entity_ids_or_uuids, id="comp_entity_ids_or_uuids"),
        pytest.param(cv.entity_domain("sensor"), id="entity_domain"),
        pytest.param(cv.entities_domain("sensor"), id="entities_domain"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(True, id="bool"),
        pytest.param(4, id="int"),
        pytest.param(1.5, id="float"),
    ],
)
def test_entity_ids_non_iterable(validator: Callable[[Any], Any], value: Any) -> None:
    """Test entity ID validators reject non-string scalars with Invalid."""
    with pytest.raises(probatio.Invalid):
        validator(value)


def test_entities_domain() -> None:
    """Test entities domain validation."""
    schema = probatio.Schema(cv.entities_domain("sensor"))

    options = (
        None,
        "",
        "invalid_entity",
        ["sensor.light", "cover.demo"],
        ["sensor.light", "sensor_invalid"],
    )

    for value in options:
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    options = ("sensor.light", ["SENSOR.light"], ["sensor.light", "sensor.demo"])
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, sensor.demo ") == ["sensor.light", "sensor.demo"]
    assert schema(["sensor.light", "SENSOR.demo"]) == ["sensor.light", "sensor.demo"]


def test_ensure_list_csv() -> None:
    """Test ensure_list_csv."""
    schema = probatio.Schema(cv.ensure_list_csv)

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
        with pytest.raises(probatio.MultipleInvalid):
            cv.EVENT_SCHEMA(value)

    options = (
        {"event": "state_changed"},
        {"event": "state_changed", "event_data": {"hello": "world"}},
    )
    for value in options:
        cv.EVENT_SCHEMA(value)


def test_icon() -> None:
    """Test icon validation."""
    schema = probatio.Schema(cv.icon)

    for value in (False, "work", "mdi:wo rk", "mdi:\twork", "mdi: work"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    schema("mdi:work")
    schema("custom:prefix")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("mdi:work\n", id="trailing_newline"),
        pytest.param(" mdi:work", id="leading_space"),
        pytest.param("\tmdi:work  ", id="tab_and_trailing_spaces"),
    ],
)
def test_icon_strips_surrounding_whitespace(value: str) -> None:
    """Test icon validation strips surrounding whitespace."""
    assert cv.icon(value) == "mdi:work"


def test_time_period() -> None:
    """Test time_period validation."""
    schema = probatio.Schema(cv.time_period)

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
        with pytest.raises(probatio.MultipleInvalid):
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


@pytest.mark.parametrize(
    "validator",
    [
        pytest.param(cv.time_period, id="time_period"),
        pytest.param(cv.positive_time_period, id="positive_time_period"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(math.inf, id="float_inf"),
        pytest.param("inf", id="str_inf"),
        pytest.param("-inf", id="str_neg_inf"),
        pytest.param(10**20, id="huge_seconds"),
        pytest.param("99999999999:00", id="huge_hours"),
        pytest.param("0:0:inf", id="inf_seconds_field"),
        pytest.param({"days": math.inf}, id="dict_inf_days"),
        pytest.param({"days": 1e10}, id="dict_huge_days"),
    ],
)
def test_time_period_overflow(validator: Callable[[Any], Any], value: Any) -> None:
    """Test time_period rejects periods that overflow timedelta."""
    with pytest.raises(probatio.Invalid):
        probatio.Schema(validator)(value)


def test_remove_falsy() -> None:
    """Test remove falsy."""
    assert cv.remove_falsy([0, None, 1, "1", {}, [], ""]) == [1, "1"]


def test_service() -> None:
    """Test service validation."""
    schema = probatio.Schema(cv.service)

    with pytest.raises(probatio.MultipleInvalid):
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
        {
            "action": "light.turn_on",
            "target": {
                "area_id": "kitchen",
                "exclude": {"entity_id": "light.pantry"},
            },
        },
        {
            "action": "light.turn_on",
            "target": {
                "area_id": "{{ 'kitchen' }}",
                "exclude": {"entity_id": "light.pantry"},
            },
        },
        {"action": "light.turn_on", "target": "{{ {'area_id': 'kitchen'} }}"},
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
        {
            "action": "light.turn_on",
            "target": {"exclude": {"entity_id": "light.pantry"}},
        },
    ],
)
def test_invalid_service_schema(
    hass: HomeAssistant, config: dict[str, Any] | None
) -> None:
    """Test service_schema validation fails."""
    with pytest.raises(probatio.MultipleInvalid):
        cv.SERVICE_SCHEMA(config)


def test_entity_service_schema() -> None:
    """Test make_entity_service_schema validation."""
    schema = cv.make_entity_service_schema(
        {
            probatio.Required("required"): cv.positive_int,
            probatio.Optional("optional"): cv.string,
        }
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
        with pytest.raises(probatio.MultipleInvalid):
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


def test_entity_service_schema_exclude() -> None:
    """Test make_entity_service_schema validates the exclude block."""
    schema = cv.make_entity_service_schema({})

    invalid = (
        # An exclude block alone doesn't target anything
        {"exclude": {"entity_id": "light.kitchen"}},
        # Exclude blocks can't be nested
        {"area_id": "kitchen", "exclude": {"exclude": {"area_id": "pantry"}}},
        # all and none are not supported in the exclude block
        {"area_id": "kitchen", "exclude": {"entity_id": "all"}},
        {"area_id": "kitchen", "exclude": {"entity_id": "none"}},
        {"area_id": "kitchen", "exclude": {"unknown": "pantry"}},
        {"area_id": "kitchen", "exclude": "light.kitchen"},
        # Unlike the target, the exclude block only accepts strict entity IDs
        {"area_id": "kitchen", "exclude": {"entity_id": "light.kitchen, light.pantry"}},
        {"area_id": "kitchen", "exclude": {"entity_id": "Light.Kitchen"}},
        {
            "area_id": "kitchen",
            "exclude": {"entity_id": "0123456789abcdef0123456789abcdef"},
        },
    )
    for value in invalid:
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    assert schema(
        {
            "entity_id": "all",
            "exclude": {
                "entity_id": ["light.kitchen", "light.pantry"],
                "device_id": "a_device",
                "area_id": "kitchen",
                "floor_id": "ground_floor",
                "label_id": "christmas",
            },
        }
    ) == {
        "entity_id": "all",
        "exclude": {
            "entity_id": ["light.kitchen", "light.pantry"],
            "device_id": ["a_device"],
            "area_id": ["kitchen"],
            "floor_id": ["ground_floor"],
            "label_id": ["christmas"],
        },
    }


@pytest.mark.parametrize(
    "schema",
    [
        probatio.Schema(cv.TARGET_FIELDS),
        probatio.Schema(cv.TARGET_SERVICE_FIELDS),
        probatio.Schema(cv._TARGET_SERVICE_FIELDS_TEMPLATED),
    ],
)
def test_target_fields_exclude(schema: probatio.Schema) -> None:
    """Test the exclude block of the target field schemas."""
    assert schema({"area_id": "kitchen", "exclude": {"label_id": "christmas"}}) == {
        "area_id": ["kitchen"],
        "exclude": {"label_id": ["christmas"]},
    }

    for value in (
        {"area_id": "kitchen", "exclude": {"exclude": {"area_id": "pantry"}}},
        {"area_id": "kitchen", "exclude": {"entity_id": "all"}},
        {"area_id": "kitchen", "exclude": {"entity_id": "light.kitchen, light.pantry"}},
        {"area_id": "kitchen", "exclude": {"entity_id": "Light.Kitchen"}},
        {
            "area_id": "kitchen",
            "exclude": {"entity_id": "0123456789abcdef0123456789abcdef"},
        },
    ):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({}, id="empty"),
        pytest.param({"area_id": ["kitchen"]}, id="no_exclude"),
        pytest.param(
            {"area_id": ["kitchen"], "exclude": {"label_id": ["christmas"]}},
            id="target_and_exclude",
        ),
    ],
)
def test_exclude_requires_target_valid(value: dict[str, Any]) -> None:
    """Test targets which are accepted by exclude_requires_target."""
    assert cv.exclude_requires_target(value) == value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({"exclude": {"label_id": ["christmas"]}}, id="exclude_only"),
        pytest.param(
            {"entity_id": [], "exclude": {"label_id": ["christmas"]}},
            id="empty_target_and_exclude",
        ),
    ],
)
def test_exclude_requires_target_invalid(value: dict[str, Any]) -> None:
    """Test a target consisting of only an exclude block is rejected."""
    with pytest.raises(
        probatio.Invalid, match="an exclude block requires a target to exclude from"
    ):
        cv.exclude_requires_target(value)


def test_entity_service_schema_with_metadata() -> None:
    """Test make_entity_service_schema with overridden metadata key."""
    schema = cv.make_entity_service_schema(
        {probatio.Required("metadata"): cv.positive_int}
    )

    options = ({"metadata": {"some": "frontend_stuff"}, "entity_id": "light.kitchen"},)
    for value in options:
        with pytest.raises(probatio.MultipleInvalid):
            cv.SERVICE_SCHEMA(value)

    options = ({"metadata": 1, "entity_id": "light.kitchen"},)
    for value in options:
        validated = schema(value)
        assert "metadata" in validated


def test_slug() -> None:
    """Test slug validation."""
    schema = probatio.Schema(cv.slug)

    for value in (None, "hello world"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in (12345, "hello"):
        schema(value)


def test_string(hass: HomeAssistant) -> None:
    """Test string validation."""
    schema = probatio.Schema(cv.string)

    with pytest.raises(probatio.Invalid):
        schema(None)

    with pytest.raises(probatio.Invalid):
        schema([])

    with pytest.raises(probatio.Invalid):
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
    schema = probatio.Schema(cv.string_with_no_html)

    with pytest.raises(probatio.Invalid):
        schema("This has HTML in it <a>Link</a>")

    with pytest.raises(probatio.Invalid):
        schema("<b>Bold</b>")

    with pytest.raises(probatio.Invalid):
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
    schema = probatio.Schema(cv.temperature_unit)

    with pytest.raises(probatio.MultipleInvalid):
        schema("K")

    schema("C")
    schema("F")


def test_x10_address() -> None:
    """Test x10 addr validator."""
    schema = probatio.Schema(cv.x10_address)
    with pytest.raises(probatio.Invalid):
        schema("Q1")
    with pytest.raises(probatio.Invalid):
        schema("q55")
    with pytest.raises(probatio.Invalid):
        schema("garbage_addr")
    with pytest.raises(probatio.Invalid):
        schema("a1\n")

    schema("a1")
    schema("C11")


def test_template(hass: HomeAssistant) -> None:
    """Test template validator."""
    schema = probatio.Schema(cv.template)

    for value in (
        None,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
    ):
        with pytest.raises(probatio.Invalid):
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
    schema = probatio.Schema(cv.template)

    for value in (
        None,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
        # Filter added as an extension by Home Assistant
        "{{ ['group.foo']|expand|map(attribute='entity_id')|list }}",
    ):
        with pytest.raises(probatio.Invalid):
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
        with pytest.raises(
            probatio.Invalid, match="Validates schema outside the event loop"
        ):
            await hass.async_add_executor_job(schema, value)


def test_dynamic_template(hass: HomeAssistant) -> None:
    """Test dynamic template validator."""
    schema = probatio.Schema(cv.dynamic_template)

    for value in (
        None,
        1,
        "{{ partial_print }",
        "{% if True %}Hello",
        ["test"],
        "just a string",
    ):
        with pytest.raises(probatio.Invalid):
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


@pytest.mark.usefixtures("hass")
def test_template_complex() -> None:
    """Test template_complex validator."""
    schema = probatio.Schema(cv.template_complex)

    for value in ("{{ partial_print }", "{% if True %}Hello"):
        with pytest.raises(probatio.MultipleInvalid):
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


INVALID_TEMPLATE = "{{ partial_print }"
INVALID_TEMPLATE_MESSAGE = "invalid template (TemplateSyntaxError: unexpected '}')"


@pytest.mark.usefixtures("hass")
@pytest.mark.parametrize(
    ("value", "expected_path"),
    [
        pytest.param(INVALID_TEMPLATE, [], id="string"),
        pytest.param(["{{ beer }}", INVALID_TEMPLATE], [1], id="list_index"),
        pytest.param({"a": "{{ beer }}", "b": INVALID_TEMPLATE}, ["b"], id="dict_key"),
        pytest.param({INVALID_TEMPLATE: 1}, [INVALID_TEMPLATE], id="dict_template_key"),
        pytest.param(
            {"data": {"a": ["{{ beer }}", {"b": INVALID_TEMPLATE}]}},
            ["data", "a", 1, "b"],
            id="nested",
        ),
    ],
)
def test_template_complex_error_path(value: Any, expected_path: list[Any]) -> None:
    """Test template_complex reports the path of the failing element."""
    with pytest.raises(probatio.Invalid) as excinfo:
        cv.template_complex(value)

    assert excinfo.value.path == expected_path
    assert excinfo.value.error_message == INVALID_TEMPLATE_MESSAGE


@pytest.mark.usefixtures("hass")
@pytest.mark.parametrize(
    ("validator", "value", "expected_path", "expected_message"),
    [
        pytest.param(
            probatio.Any(cv.string, cv.template_complex),
            {"a": [INVALID_TEMPLATE]},
            ["a", 0],
            INVALID_TEMPLATE_MESSAGE,
            id="any_string_template_complex",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {"action": "light.turn_on", "data": {"a": INVALID_TEMPLATE}},
            ["data", "a"],
            INVALID_TEMPLATE_MESSAGE,
            id="service_data",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {"action": "light.turn_on", "data_template": {"a": [INVALID_TEMPLATE]}},
            ["data_template", "a", 0],
            INVALID_TEMPLATE_MESSAGE,
            id="service_data_template",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {"action": "light.turn_on", "data": [INVALID_TEMPLATE]},
            ["data"],
            "template value should be a string",
            id="service_data_not_a_dict",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {
                "action": "light.turn_on",
                "target": {"entity_id": ["light.kitchen", INVALID_TEMPLATE]},
            },
            ["target", "entity_id", 1],
            INVALID_TEMPLATE_MESSAGE,
            id="service_target_entity_id",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {
                "action": "light.turn_on",
                "target": {
                    "area_id": "kitchen",
                    "exclude": {"entity_id": ["light.kitchen", INVALID_TEMPLATE]},
                },
            },
            ["target", "exclude", "entity_id", 1],
            f"Entity ID {INVALID_TEMPLATE} is not a valid entity ID",
            id="service_target_exclude_entity_id",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {
                "action": "light.turn_on",
                "target": {
                    "area_id": "kitchen",
                    "exclude": {"entity_id": [[INVALID_TEMPLATE]]},
                },
            },
            ["target", "exclude", "entity_id", 0, 0],
            INVALID_TEMPLATE_MESSAGE,
            id="service_target_exclude_entity_id_nested_list",
        ),
        pytest.param(
            cv.SERVICE_SCHEMA,
            {"action": "light.turn_on", "target": {"entity_id": INVALID_TEMPLATE}},
            ["target", "entity_id"],
            f"Entity {INVALID_TEMPLATE} is neither a valid entity ID nor a valid UUID",
            id="service_target_entity_id_not_a_list",
        ),
        pytest.param(
            selector.TargetSelector(),
            {"entity_id": ["light.kitchen", INVALID_TEMPLATE]},
            ["entity_id", 1],
            INVALID_TEMPLATE_MESSAGE,
            id="target_selector_entity_id",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"repeat": {"for_each": ["a", INVALID_TEMPLATE], "sequence": []}}],
            [0, "repeat", "for_each", 1],
            INVALID_TEMPLATE_MESSAGE,
            id="repeat_for_each",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"repeat": {"for_each": {"a": INVALID_TEMPLATE}, "sequence": []}}],
            [0, "repeat", "for_each"],
            "template value should be a string",
            id="repeat_for_each_not_a_list",
        ),
        pytest.param(
            cv.positive_time_period_template,
            {"hours": 1, "minutes": INVALID_TEMPLATE},
            ["minutes"],
            "expected float",
            id="positive_time_period_template",
        ),
    ],
)
def test_template_complex_any_branch_error(
    validator: Any, value: Any, expected_path: list[Any], expected_message: str
) -> None:
    """Test which error wins when template_complex is one branch of an Any.

    Any reports the error with the longest path, and the first one on a tie.
    """
    with pytest.raises(probatio.Invalid) as excinfo:
        probatio.Schema(validator)(value)

    assert excinfo.value.path == expected_path
    assert excinfo.value.error_message == expected_message


def test_time_zone() -> None:
    """Test time zone validation."""
    schema = probatio.Schema(cv.time_zone)

    with pytest.raises(probatio.MultipleInvalid):
        schema("America/Do_Not_Exist")

    schema("America/Los_Angeles")
    schema("UTC")


def test_date() -> None:
    """Test date validation."""
    schema = probatio.Schema(cv.date)

    for value in ("Not a date", "23:42", "2016-11-23T18:59:08"):
        with pytest.raises(probatio.Invalid):
            schema(value)

    schema(dt_util.now().date())
    schema("2016-11-23")


def test_time() -> None:
    """Test date validation."""
    schema = probatio.Schema(cv.time)

    for value in (
        "Not a time",
        "2016-11-23",
        "2016-11-23T18:59:08",
        "0:2147483648",
    ):
        with pytest.raises(probatio.Invalid):
            schema(value)

    schema(dt_util.now().time())
    schema("23:42:00")
    schema("23:42")


def test_datetime() -> None:
    """Test date time validation."""
    schema = probatio.Schema(cv.datetime)
    for value in (date.today(), "Wrong DateTime"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    schema(dt_util.now())
    schema("2016-11-23T18:59:08")


def test_multi_select() -> None:
    """Test multi select validation.

    Expected behavior:
        - Will not accept any input but a list
        - Will not accept selections outside of configured scope
    """
    schema = probatio.Schema(cv.multi_select({"paulus": "Paulus", "robban": "Robban"}))

    with pytest.raises(probatio.Invalid):
        schema("robban")
    with pytest.raises(probatio.Invalid):
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


def test_selector_with_context_in_serializer() -> None:
    """Test selector with context with custom_serializer."""
    assert cv.custom_serializer(
        selector.UnitOfMeasurementSelector(
            selector.UnitOfMeasurementSelectorConfig(
                context={"filter_device_class": "device_class"}
            )
        )
    ) == {
        "selector": {
            "unit_of_measurement": {"context": {"filter_device_class": "device_class"}}
        },
    }


def test_selector_context_in_field_list() -> None:
    """Test selector context is only added to the field that sets it."""
    schema = probatio.Schema(
        {
            probatio.Optional("device_class"): selector.DeviceClassSelector(
                selector.DeviceClassSelectorConfig(domain="sensor")
            ),
            probatio.Optional(
                "unit_of_measurement"
            ): selector.UnitOfMeasurementSelector(
                selector.UnitOfMeasurementSelectorConfig(
                    context={"filter_device_class": "device_class"}
                )
            ),
        }
    )
    assert probatio.to_field_list(schema, custom_serializer=cv.custom_serializer) == [
        {
            "name": "device_class",
            "optional": True,
            "required": False,
            "selector": {"device_class": {"domain": "sensor", "multiple": False}},
        },
        {
            "name": "unit_of_measurement",
            "optional": True,
            "required": False,
            "selector": {
                "unit_of_measurement": {
                    "context": {"filter_device_class": "device_class"}
                }
            },
        },
    ]


def test_positive_time_period_dict_in_serializer() -> None:
    """Test positive_time_period_dict with custom_serializer."""
    assert cv.custom_serializer(cv.positive_time_period_dict) == {
        "type": "positive_time_period_dict",
    }


@pytest.fixture
def schema():
    """Create a schema used for testing deprecation."""
    return probatio.Schema(
        {"venus": cv.boolean, "mars": cv.boolean, "jupiter": cv.boolean}
    )


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
    deprecated_schema = probatio.All(cv.deprecated("mars"), schema)

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
    """Test removed or deprecation options and fail config validation.

    Expected behavior:
        - Outputs the appropriate deprecation or removed
          from support error if key is detected
    """
    removed_schema = probatio.All(cv.deprecated("mars", raise_if_present=True), schema)

    test_data = {"mars": True}
    with pytest.raises(probatio.Invalid) as excinfo:
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

    deprecated_schema = probatio.All(cv.removed("mars"), schema)

    test_data = {"mars": True}
    with pytest.raises(probatio.Invalid) as excinfo:
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
    deprecated_schema = probatio.All(
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


@pytest.mark.parametrize(
    ("replacement_key", "expected_output", "expected_message"),
    [
        pytest.param(
            None,
            {"mars": True},
            "The 'mars' option is deprecated and will be removed in Home Assistant "
            "2027.6, please remove it from your configuration",
            id="no_replacement_key",
        ),
        pytest.param(
            "jupiter",
            {"jupiter": True},
            "The 'mars' option is deprecated and will be removed in Home Assistant "
            "2027.6, please replace it with 'jupiter'",
            id="replacement_key",
        ),
    ],
)
def test_deprecated_with_breaks_in_ha_version(
    caplog: pytest.LogCaptureFixture,
    schema: probatio.Schema,
    replacement_key: str | None,
    expected_output: dict[str, bool],
    expected_message: str,
) -> None:
    """Test the deprecation warning mentions the version the key is removed in."""
    deprecated_schema = probatio.All(
        cv.deprecated(
            "mars", replacement_key=replacement_key, breaks_in_ha_version="2027.6"
        ),
        schema,
    )

    output = deprecated_schema({"mars": True})
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert expected_message in caplog.text
    assert output == expected_output


def test_deprecated_with_breaks_in_ha_version_and_raise(
    schema: probatio.Schema,
) -> None:
    """Test the raised error mentions the version the key is removed in."""
    deprecated_schema = probatio.All(
        cv.deprecated("mars", raise_if_present=True, breaks_in_ha_version="2027.6"),
        schema,
    )

    with pytest.raises(
        probatio.Invalid,
        match=(
            "The 'mars' option is deprecated and will be removed in Home Assistant "
            "2027.6, please remove it from your configuration"
        ),
    ):
        deprecated_schema({"mars": True})


def test_deprecated_with_default(caplog: pytest.LogCaptureFixture, schema) -> None:
    """Test deprecation behaves correctly with a default value.

    This is likely a scenario that would never occur.

    Expected behavior:
        - Behaves identically as when the default value was not present
    """
    deprecated_schema = probatio.All(cv.deprecated("mars", default=False), schema)

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
    deprecated_schema = probatio.All(
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

    deprecated_schema_with_default = probatio.All(
        probatio.Schema(
            {
                "venus": cv.boolean,
                probatio.Optional("mars", default=False): cv.boolean,
                probatio.Optional("jupiter", default=False): cv.boolean,
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
    """Test logger outputs correct message if line and file attr is available."""
    file: str = "configuration.yaml"
    line: int = 54

    # test as deprecated option
    replacement_key = "jupiter"
    option_status = "is deprecated"
    replacement = (
        f"'mars' option near {file}:{line} {option_status},"
        f" please replace it with '{replacement_key}'"
    )
    config = OrderedDict([("mars", "blah")])
    config.__config_file__ = file
    config.__line__ = line

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
    replacement = (
        f"'mars' option near {file}:{line} {option_status},"
        " please remove it from your configuration"
    )
    config = OrderedDict([("mars", "blah")])
    config.__config_file__ = file
    config.__line__ = line

    validated = cv.removed("mars", default=False, raise_if_present=False)(config)
    assert "mars" not in validated  # Removed because by cv.removed

    assert len(caplog.records) == 1
    assert replacement in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0


def test_deprecated_logger_with_one_config_attribute(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logger message when only one of line/file attr is available."""
    file: str = "configuration.yaml"
    line: int = 54
    replacement = f"'mars' option near {file}:{line} is deprecated"
    config = OrderedDict([("mars", "blah")])
    config.__config_file__ = file

    cv.deprecated("mars", replacement_key="jupiter", default=False)(config)

    assert len(caplog.records) == 1
    assert replacement not in caplog.text
    assert (
        "The 'mars' option is deprecated, please replace it with 'jupiter'"
    ) in caplog.text

    caplog.clear()
    assert len(caplog.records) == 0

    config = OrderedDict([("mars", "blah")])
    config.__line__ = line

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
    """Test logger message when line and file attr is not available."""
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


@pytest.mark.parametrize(
    ("validator", "option_status"),
    [
        pytest.param(cv.deprecated, "is deprecated", id="deprecated"),
        pytest.param(
            partial(cv.removed, raise_if_present=False),
            "has been removed",
            id="removed",
        ),
    ],
)
@pytest.mark.parametrize(
    "preprocess",
    [
        pytest.param(lambda config: config, id="raw_loader_output"),
        pytest.param(probatio.Schema(dict), id="pass_through_schema"),
        pytest.param(
            probatio.Schema({}, extra=probatio.ALLOW_EXTRA),
            id="rebuilding_schema",
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "The mapping engine allocates a fresh container and never copies "
                    "the __config_file__/__line__ slots, so _deprecated_or_removed "
                    "takes its 'except AttributeError' branch and logs no location."
                ),
            ),
        ),
        pytest.param(
            cv.PLATFORM_SCHEMA_BASE,
            id="platform_schema_base",
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "Same rebuild, through the real PLATFORM_SCHEMA_BASE that "
                    "check_config.py runs before the platform's own PLATFORM_SCHEMA."
                ),
            ),
        ),
    ],
)
def test_deprecated_or_removed_location_survives_schema_rebuild(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    validator: Callable[..., Callable[[dict], dict]],
    option_status: str,
    preprocess: Callable[[dict], dict],
) -> None:
    """Test the location prefix survives a schema the config was passed through.

    The config is built with the real YAML loader so the annotation is the one
    production gets, not a hand-set attribute.
    """
    # Note: Unlike find_annotation, which reads the location off the mapping key,
    # _deprecated_or_removed reads it off the container itself, so a schema that
    # rebuilds the container silently drops the "near <file>:<line>" prefix. That is
    # what check_config.py does when it hands the already validated p_validated to
    # the platform's own PLATFORM_SCHEMA, where the cv.deprecated calls of broadlink,
    # canary, mvglive and integration live.

    config_file = tmp_path / "configuration.yaml"
    config_file.write_text("platform: test_platform\nmars: blah\n", encoding="utf8")
    config = load_yaml_dict(str(config_file))

    validator("mars", default=False)(preprocess(config))

    assert len(caplog.records) == 1
    assert f"The 'mars' option near {config_file}:1 {option_status}" in caplog.text


def test_key_dependency() -> None:
    """Test key_dependency validator."""
    schema = probatio.Schema(cv.key_dependency("beer", "soda"))

    options = {"beer": None}
    for value in options:
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    options = ({"beer": None, "soda": None}, {"soda": None}, {})
    for value in options:
        schema(value)


def test_has_at_most_one_key() -> None:
    """Test has_at_most_one_key validator."""
    schema = probatio.Schema(cv.has_at_most_one_key("beer", "soda"))

    for value in (None, [], {"beer": None, "soda": None}):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in (
        {},
        {"beer": None},
        {"soda": None},
        {probatio.Optional("soda"): None},
    ):
        schema(value)


def test_has_at_least_one_key() -> None:
    """Test has_at_least_one_key validator."""
    schema = probatio.Schema(cv.has_at_least_one_key("beer", "soda"))

    for value in (None, [], {}, {"wine": None}):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ({"beer": None}, {"soda": None}, {probatio.Required("soda"): None}):
        schema(value)


def test_enum() -> None:
    """Test enum validator."""

    class TestEnum(enum.Enum):
        """Test enum."""

        value1 = "Value 1"
        value2 = "Value 2"

    schema = probatio.Schema(cv.enum(TestEnum))

    with pytest.raises(probatio.Invalid):
        schema("value3")


def test_socket_timeout() -> None:
    """Test socket timeout validator."""
    schema = probatio.Schema(cv.socket_timeout)

    with pytest.raises(probatio.Invalid):
        schema(0.0)

    with pytest.raises(probatio.Invalid):
        schema(-1)

    assert schema(None) == _GLOBAL_DEFAULT_TIMEOUT

    assert schema(1) == 1.0


def test_matches_regex() -> None:
    """Test matches_regex validator."""
    schema = probatio.Schema(cv.matches_regex(".*uiae.*"))

    with pytest.raises(probatio.Invalid):
        schema(1.0)

    with pytest.raises(probatio.Invalid):
        schema("  nrtd   ")

    test_str = "This is a test including uiae."
    assert schema(test_str) == test_str


def test_is_regex() -> None:
    """Test the is_regex validator."""
    schema = probatio.Schema(cv.is_regex)

    with pytest.raises(probatio.Invalid):
        schema("(")

    with pytest.raises(probatio.Invalid):
        schema({"a dict": "is not a regex"})

    valid_re = ".*"
    schema(valid_re)


def test_comp_entity_ids() -> None:
    """Test config validation for component entity IDs."""
    schema = probatio.Schema(cv.comp_entity_ids)

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
        with pytest.raises(probatio.Invalid):
            schema(invalid)


@pytest.mark.parametrize(
    "validator",
    [
        pytest.param(cv.comp_entity_ids, id="comp_entity_ids"),
        pytest.param(cv.comp_entity_ids_or_uuids, id="comp_entity_ids_or_uuids"),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("all", "all", id="all"),
        pytest.param("ALL", "all", id="all_upper"),
        pytest.param("none", "none", id="none"),
        pytest.param("NoNe", "none", id="none_mixed_case"),
        pytest.param(None, "none", id="none_value"),
        pytest.param([], [], id="empty_list"),
        pytest.param("light.kitchen", ["light.kitchen"], id="string"),
        pytest.param("LIGHT.Kitchen", ["light.kitchen"], id="string_upper"),
        pytest.param(
            "light.kitchen, light.ceiling",
            ["light.kitchen", "light.ceiling"],
            id="comma_string",
        ),
        pytest.param(
            ["light.kitchen", "light.ceiling"],
            ["light.kitchen", "light.ceiling"],
            id="list",
        ),
    ],
)
def test_comp_entity_ids_valid(
    validator: Callable[[Any], Any], value: Any, expected: str | list[str]
) -> None:
    """Test component entity ID validators accept and normalize valid values."""
    assert validator(value) == expected


@pytest.mark.parametrize(
    ("validator", "value", "message"),
    [
        pytest.param(
            cv.comp_entity_ids,
            "not-entity-id",
            "Entity ID not-entity-id is an invalid entity ID",
            id="comp_entity_ids-string",
        ),
        pytest.param(
            cv.comp_entity_ids,
            ["light.kitchen", "not-entity-id"],
            "Entity ID not-entity-id is an invalid entity ID",
            id="comp_entity_ids-list",
        ),
        pytest.param(
            cv.comp_entity_ids,
            ["all"],
            "Entity ID all is an invalid entity ID",
            id="comp_entity_ids-all_in_list",
        ),
        pytest.param(
            cv.comp_entity_ids,
            4,
            "Entity IDs must be a string or a list",
            id="comp_entity_ids-int",
        ),
        pytest.param(
            cv.comp_entity_ids_or_uuids,
            "not-entity-id",
            "Entity not-entity-id is neither a valid entity ID nor a valid UUID",
            id="comp_entity_ids_or_uuids-string",
        ),
        pytest.param(
            cv.comp_entity_ids_or_uuids,
            ["light.kitchen", "not-entity-id"],
            "Entity not-entity-id is neither a valid entity ID nor a valid UUID",
            id="comp_entity_ids_or_uuids-list",
        ),
        pytest.param(
            cv.comp_entity_ids_or_uuids,
            4,
            "Entity IDs must be a string or a list",
            id="comp_entity_ids_or_uuids-int",
        ),
        pytest.param(
            cv.make_entity_service_schema({}),
            {"entity_id": "not-entity-id"},
            "Entity ID not-entity-id is an invalid entity ID at 'entity_id'",
            id="entity_service_schema-string",
        ),
        pytest.param(
            cv.make_entity_service_schema({}),
            {"entity_id": ["light.kitchen", "not-entity-id"]},
            "Entity ID not-entity-id is an invalid entity ID at 'entity_id'",
            id="entity_service_schema-list",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"action": "light.turn_on", "target": {"entity_id": "not-entity-id"}}],
            "Entity not-entity-id is neither a valid entity ID nor a valid UUID"
            " at '[0].target.entity_id'",
            id="script_schema-target",
        ),
    ],
)
def test_comp_entity_ids_invalid_message(
    validator: Callable[[Any], Any], value: Any, message: str
) -> None:
    """Test component entity ID validators report the entity ID error."""
    with pytest.raises(probatio.Invalid) as excinfo:
        validator(value)
    assert str(excinfo.value) == message


def test_uuid4_hex(caplog: pytest.LogCaptureFixture) -> None:
    """Test uuid validation."""
    schema = probatio.Schema(cv.uuid4_hex)

    for value in ("Not a hex string", "0", 0):
        with pytest.raises(probatio.Invalid):
            schema(value)

    with pytest.raises(probatio.Invalid):
        # the 13th char should be 4
        schema("a03d31b22eee1acc9b90eec40be6ed23")

    with pytest.raises(probatio.Invalid):
        # the 17th char should be 8-a
        schema("a03d31b22eee4acc7b90eec40be6ed23")

    _hex = uuid.uuid4().hex
    assert schema(_hex) == _hex
    assert schema(_hex.upper()) == _hex


def test_key_value_schemas() -> None:
    """Test key value schemas."""
    schema = probatio.Schema(
        cv.key_value_schemas(
            "mode",
            {
                "number": probatio.Schema({"mode": "number", "data": int}),
                "string": probatio.Schema({"mode": "string", "data": str}),
            },
        )
    )

    with pytest.raises(probatio.Invalid) as excinfo:
        schema(True)
    assert str(excinfo.value) == "Expected a dictionary"

    for mode in None, {"a": "dict"}, "invalid":
        with pytest.raises(probatio.Invalid) as excinfo:
            schema({"mode": mode})
        assert (
            str(excinfo.value)
            == f"Unexpected value for mode: '{mode}'. Expected number, string"
        )

    with pytest.raises(probatio.Invalid) as excinfo:
        schema({"mode": "number", "data": "string-value"})
    assert str(excinfo.value) == "expected int at 'data'"

    with pytest.raises(probatio.Invalid) as excinfo:
        schema({"mode": "string", "data": 1})
    assert str(excinfo.value) == "expected str at 'data'"

    for mode, data in (("number", 1), ("string", "hello")):
        schema({"mode": mode, "data": data})


@pytest.mark.usefixtures("hass")
def test_key_value_schemas_with_default() -> None:
    """Test key value schemas."""
    schema = probatio.Schema(
        cv.key_value_schemas(
            "mode",
            {
                "number": probatio.Schema({"mode": "number", "data": int}),
                "string": probatio.Schema({"mode": "string", "data": str}),
            },
            probatio.Schema({"mode": cv.dynamic_template}),
            "a cool template",
        )
    )

    with pytest.raises(probatio.Invalid) as excinfo:
        schema(True)
    assert str(excinfo.value) == "Expected a dictionary"

    for mode in None, {"a": "dict"}, "invalid":
        with pytest.raises(probatio.Invalid) as excinfo:
            schema({"mode": mode})
        assert (
            str(excinfo.value) == f"Unexpected value for mode: '{mode}'."
            " Expected number, string, a cool template"
        )

    with pytest.raises(probatio.Invalid) as excinfo:
        schema({"mode": "number", "data": "string-value"})
    assert str(excinfo.value) == "expected int at 'data'"

    with pytest.raises(probatio.Invalid) as excinfo:
        schema({"mode": "string", "data": 1})
    assert str(excinfo.value) == "expected str at 'data'"

    for mode, data in (("number", 1), ("string", "hello")):
        schema({"mode": mode, "data": data})
    schema({"mode": "{{ 1 + 1}}"})


@pytest.mark.usefixtures("hass")
def test_key_value_schemas_with_default_no_list_alternatives() -> None:
    """Test key value schemas."""
    schema = probatio.Schema(
        cv.key_value_schemas(
            "mode",
            {
                "number": probatio.Schema({"mode": "number", "data": int}),
                "string": probatio.Schema({"mode": "string", "data": str}),
            },
            probatio.Schema({"mode": cv.dynamic_template}),
            "a cool template",
            list_alternatives=False,
        )
    )

    with pytest.raises(probatio.Invalid) as excinfo:
        schema(True)
    assert str(excinfo.value) == "Expected a dictionary"

    for mode in None, {"a": "dict"}, "invalid":
        with pytest.raises(probatio.Invalid) as excinfo:
            schema({"mode": mode})
        assert (
            str(excinfo.value)
            == f"Unexpected value for mode: '{mode}'. Expected a cool template"
        )


@pytest.mark.usefixtures("hass")
def test_key_value_schemas_without_default_no_list_alternatives() -> None:
    """Test key value schemas."""
    with pytest.raises(ValueError) as excinfo:
        probatio.Schema(
            cv.key_value_schemas(
                "mode",
                {
                    "number": probatio.Schema({"mode": "number", "data": int}),
                    "string": probatio.Schema({"mode": "string", "data": str}),
                },
                probatio.Schema({"mode": cv.dynamic_template}),
                list_alternatives=False,
            )
        )
    assert (
        str(excinfo.value)
        == "default_description must be provided if list_alternatives is False"
    )


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ({"delay": "{{ invalid"}, "should be format 'HH:MM'"),
        ({"wait_template": "{{ invalid"}, "invalid template"),
        # The validation error message could be improved to explain that this is not
        # a valid shorthand template
        (
            {"condition": 123},
            "Unexpected value for condition: '123'. Expected a condition, a list of "
            "conditions or a valid template",
        ),
        (
            {"condition": "not", "conditions": "not a dynamic template"},
            "Expected a dictionary",
        ),
        (
            {"event": None},
            r"string value is None at 'event'",
        ),
        (
            {"device_id": None},
            r"string value is None at 'device_id'",
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
@pytest.mark.usefixtures("hass")
def test_script(caplog: pytest.LogCaptureFixture, config: dict, error: str) -> None:
    """Test script action validation is user friendly."""
    with pytest.raises(probatio.Invalid, match=error):
        cv.script_action(config)


@pytest.mark.parametrize(
    ("parallel", "expected"),
    [
        pytest.param(None, [], id="none"),
        pytest.param([None], [{"sequence": []}], id="none_branch"),
        pytest.param([[]], [{"sequence": []}], id="empty_list_branch"),
        pytest.param(
            {"delay": 1},
            [{"sequence": [{"delay": timedelta(seconds=1)}]}],
            id="single_action",
        ),
        pytest.param(
            [{"delay": 1}, [{"delay": 1}, {"delay": 1}], {"sequence": [{"delay": 1}]}],
            [
                {"sequence": [{"delay": timedelta(seconds=1)}]},
                {
                    "sequence": [
                        {"delay": timedelta(seconds=1)},
                        {"delay": timedelta(seconds=1)},
                    ]
                },
                {"sequence": [{"delay": timedelta(seconds=1)}]},
            ],
            id="action_list_and_sequence_branches",
        ),
        pytest.param(
            [{"sequence": {"delay": 1}}],
            [{"sequence": [{"delay": timedelta(seconds=1)}]}],
            id="sequence_single_action",
        ),
        pytest.param(
            [{"alias": "x", "sequence": [{"delay": 1}]}],
            [{"alias": "x", "sequence": [{"delay": timedelta(seconds=1)}]}],
            id="sequence_with_alias",
        ),
        # A branch with both an action key and a sequence key is that action
        pytest.param(
            [{"device_id": "x", "domain": "light", "sequence": [{"event": "foo"}]}],
            [
                {
                    "sequence": [
                        {
                            "device_id": "x",
                            "domain": "light",
                            "sequence": [{"event": "foo"}],
                        }
                    ]
                }
            ],
            id="device_action_with_sequence_key",
        ),
        pytest.param(
            [
                {
                    "condition": "device",
                    "device_id": "x",
                    "domain": "light",
                    "sequence": [{"event": "foo"}],
                }
            ],
            [
                {
                    "sequence": [
                        {
                            "condition": "device",
                            "device_id": "x",
                            "domain": "light",
                            "sequence": [{"event": "foo"}],
                        }
                    ]
                }
            ],
            id="device_condition_with_sequence_key",
        ),
    ],
)
def test_script_parallel_branches(
    parallel: Any, expected: list[dict[str, Any]]
) -> None:
    """Test the branches of a parallel action are wrapped in sequences."""
    assert cv.SCRIPT_SCHEMA([{"parallel": parallel}]) == [{"parallel": expected}]


@pytest.mark.parametrize(
    ("parallel", "error"),
    [
        pytest.param(
            [{"delay": "garbage"}],
            "offset garbage should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at '[0].parallel[0].delay'",
            id="action",
        ),
        pytest.param(
            {"delay": "garbage"},
            "offset garbage should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at '[0].parallel.delay'",
            id="single_action",
        ),
        pytest.param(
            [[{"delay": 1}, {"delay": "garbage"}]],
            "offset garbage should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at '[0].parallel[0][1].delay'",
            id="action_list",
        ),
        pytest.param(
            [{"sequence": [{"delay": "garbage"}]}],
            "offset garbage should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at '[0].parallel[0].sequence[0].delay'",
            id="sequence",
        ),
        pytest.param(
            [{"sequence": [{"delay": 1}], "bogus": 1}],
            "not a valid option at '[0].parallel[0].bogus'",
            id="sequence_with_extra_key",
        ),
        pytest.param(
            [{"sequence": [{"delay": 1}], "service": "a.b"}],
            "not a valid option at '[0].parallel[0].sequence'",
            id="service_with_sequence_key",
        ),
        pytest.param(
            [{"sequence": [{"delay": 1}], "variables": {"a": 1}}],
            "not a valid option at '[0].parallel[0].sequence'",
            id="variables_with_sequence_key",
        ),
        pytest.param(
            [
                {
                    "condition": "state",
                    "entity_id": "light.a",
                    "state": "on",
                    "sequence": [{"delay": 1}],
                }
            ],
            "not a valid option at '[0].parallel[0].sequence'",
            id="state_condition_with_sequence_key",
        ),
        pytest.param(
            [{"delay": 1, "sequence": [{"delay": 1}]}],
            "not a valid option at '[0].parallel[0].sequence'",
            id="delay_with_sequence_key",
        ),
        pytest.param(
            ["str"], "expected dictionary at '[0].parallel[0]'", id="string_branch"
        ),
        pytest.param(5, "expected dictionary at '[0].parallel'", id="not_a_list"),
        pytest.param(
            [{"foo": 1}],
            "Unable to determine action at '[0].parallel[0]'",
            id="unknown_action",
        ),
        pytest.param(
            [{}], "Unable to determine action at '[0].parallel[0]'", id="empty_branch"
        ),
    ],
)
def test_script_parallel_branches_invalid(parallel: Any, error: str) -> None:
    """Test the error of an invalid parallel branch has the path of the branch."""
    with pytest.raises(probatio.Invalid) as excinfo:
        cv.SCRIPT_SCHEMA([{"parallel": parallel}])
    assert str(excinfo.value) == error


_STATE_CONDITION = {"condition": "state", "entity_id": "light.a", "state": "on"}
_VALIDATED_STATE_CONDITION = {
    "condition": "state",
    "entity_id": ["light.a"],
    "state": "on",
    "match": "all",
}
_STATE_CONDITION_WITHOUT_STATE = {"condition": "state", "entity_id": "light.a"}
_INVALID_TEMPLATE_CONDITION = {"condition": "template", "value_template": "{{ bad"}
_UNKNOWN_CONDITION = {"condition": "non_existing"}

_STATE_REQUIRED = ("required key not provided", "required")
_NOT_AN_OPTION = ("not a valid option", "extra_keys_not_allowed")
_EXPECTED_DICT = ("Expected a dictionary", None)
_INVALID_TEMPLATE = (
    "invalid template (TemplateSyntaxError: unexpected end of template, "
    "expected 'end of print statement'.)",
    None,
)
_UNEXPECTED_CONDITION_NONE = (
    "Unexpected value for condition: 'None'. Expected a condition, a list of "
    "conditions or a valid template",
    None,
)
_UNEXPECTED_CONDITION_LIST = (
    f"Unexpected value for condition: '{[_STATE_CONDITION]}'. Expected a "
    "condition, a list of conditions or a valid template",
    None,
)


@pytest.mark.parametrize(
    ("schema", "config", "expected"),
    [
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            _STATE_CONDITION,
            [_VALIDATED_STATE_CONDITION],
            id="single",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [_STATE_CONDITION, _STATE_CONDITION], "alias": "x"}],
            [
                {
                    "condition": "or",
                    "conditions": [
                        _VALIDATED_STATE_CONDITION,
                        _VALIDATED_STATE_CONDITION,
                    ],
                    "alias": "x",
                }
            ],
            id="or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"and": [_STATE_CONDITION], "note": "x", "enabled": False}],
            [
                {
                    "condition": "and",
                    "conditions": [_VALIDATED_STATE_CONDITION],
                    "enabled": False,
                }
            ],
            id="and",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"not": _STATE_CONDITION}],
            [{"condition": "not", "conditions": [_VALIDATED_STATE_CONDITION]}],
            id="not_single_child",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": None}],
            [{"condition": "or", "conditions": []}],
            id="or_none",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": [_STATE_CONDITION], "alias": "x"}],
            [
                {
                    "condition": "and",
                    "conditions": [_VALIDATED_STATE_CONDITION],
                    "alias": "x",
                }
            ],
            id="list",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": []}],
            [{"condition": "and", "conditions": []}],
            id="list_empty",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [{"and": [_STATE_CONDITION, {"not": [_STATE_CONDITION]}]}]}],
            [
                {
                    "condition": "or",
                    "conditions": [
                        {
                            "condition": "and",
                            "conditions": [
                                _VALIDATED_STATE_CONDITION,
                                {
                                    "condition": "not",
                                    "conditions": [_VALIDATED_STATE_CONDITION],
                                },
                            ],
                        }
                    ],
                }
            ],
            id="nested",
        ),
        # A condition key makes it a long form condition, the shorthand key is
        # then an option of that condition
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": "light.is_on", "or": [_STATE_CONDITION]}],
            [{"condition": "light.is_on", "or": [_STATE_CONDITION]}],
            id="custom_condition_with_or",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"condition": "light.is_on", "or": [_STATE_CONDITION]}],
            [{"condition": "light.is_on", "or": [_STATE_CONDITION]}],
            id="action_custom_condition_with_or",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"or": [_STATE_CONDITION, _STATE_CONDITION]}],
            [
                {
                    "condition": "or",
                    "conditions": [
                        _VALIDATED_STATE_CONDITION,
                        _VALIDATED_STATE_CONDITION,
                    ],
                }
            ],
            id="action_or",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"condition": [_STATE_CONDITION, _STATE_CONDITION]}],
            [
                {
                    "condition": "and",
                    "conditions": [
                        _VALIDATED_STATE_CONDITION,
                        _VALIDATED_STATE_CONDITION,
                    ],
                }
            ],
            id="action_list",
        ),
    ],
)
def test_condition_shorthand(
    schema: Callable[[Any], Any], config: Any, expected: list[dict[str, Any]]
) -> None:
    """Test condition shorthands are expanded and validated."""
    assert schema(config) == expected


async def test_condition_shorthand_template(hass: HomeAssistant) -> None:
    """Test condition shorthands with a template condition."""
    validated_template = template.Template("{{ true }}", hass)

    assert cv.CONDITIONS_SCHEMA(["{{ true }}"]) == [
        {"condition": "template", "value_template": validated_template}
    ]
    assert cv.CONDITIONS_SCHEMA(
        [{"condition": [_STATE_CONDITION, "{{ true }}"], "enabled": False}]
    ) == [
        {
            "condition": "and",
            "conditions": [
                _VALIDATED_STATE_CONDITION,
                {"condition": "template", "value_template": validated_template},
            ],
            "enabled": False,
        }
    ]
    assert cv.CONDITIONS_SCHEMA(
        [{"or": [{"condition": "template", "value_template": "{{ true }}"}]}]
    ) == [
        {
            "condition": "or",
            "conditions": [
                {"condition": "template", "value_template": validated_template}
            ],
        }
    ]
    assert cv.SCRIPT_SCHEMA([{"condition": "{{ true }}"}]) == [
        {"condition": "template", "value_template": validated_template}
    ]


@pytest.mark.parametrize(
    ("schema", "config", "expected_errors"),
    [
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            _STATE_CONDITION_WITHOUT_STATE,
            {(("state",), *_STATE_REQUIRED)},
            id="single",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE],
            {((1, "state"), *_STATE_REQUIRED)},
            id="list_of_conditions",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [
                {
                    "condition": "or",
                    "conditions": [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE],
                }
            ],
            {((0, "conditions", 1, "state"), *_STATE_REQUIRED)},
            id="long_form_or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE]}],
            {((0, "or", 1, "state"), *_STATE_REQUIRED)},
            id="or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"and": [_STATE_CONDITION_WITHOUT_STATE]}],
            {((0, "and", 0, "state"), *_STATE_REQUIRED)},
            id="and",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"not": _STATE_CONDITION_WITHOUT_STATE}],
            {((0, "not", "state"), *_STATE_REQUIRED)},
            id="not_single_child",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE]}],
            {((0, "condition", 1, "state"), *_STATE_REQUIRED)},
            id="list",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [
                {
                    "or": [
                        {
                            "and": [
                                _STATE_CONDITION,
                                {"not": [_STATE_CONDITION_WITHOUT_STATE]},
                            ]
                        }
                    ]
                }
            ],
            {((0, "or", 0, "and", 1, "not", 0, "state"), *_STATE_REQUIRED)},
            id="nested",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [
                {
                    "or": [
                        _STATE_CONDITION_WITHOUT_STATE,
                        _STATE_CONDITION,
                        _STATE_CONDITION_WITHOUT_STATE,
                    ]
                }
            ],
            {
                ((0, "or", 0, "state"), *_STATE_REQUIRED),
                ((0, "or", 2, "state"), *_STATE_REQUIRED),
            },
            id="or_two_invalid_children",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [_STATE_CONDITION], "bogus": 1}],
            {((0, "bogus"), *_NOT_AN_OPTION)},
            id="or_extra_key",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": [_STATE_CONDITION], "bogus": 1}],
            {((0, "bogus"), *_NOT_AN_OPTION)},
            id="list_extra_key",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"and": [_STATE_CONDITION], "or": [_STATE_CONDITION]}],
            {((0, "or"), *_NOT_AN_OPTION)},
            id="and_with_or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"and": [_STATE_CONDITION_WITHOUT_STATE], "or": [_STATE_CONDITION]}],
            {
                ((0, "and", 0, "state"), *_STATE_REQUIRED),
                ((0, "or"), *_NOT_AN_OPTION),
            },
            id="invalid_and_with_or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": [_STATE_CONDITION], "and": [_STATE_CONDITION]}],
            {((0, "and"), *_NOT_AN_OPTION)},
            id="list_with_and",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": 5}],
            {((0, "or"), *_EXPECTED_DICT)},
            id="or_not_a_condition",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [[_STATE_CONDITION]]}],
            {((0, "or", 0), *_EXPECTED_DICT)},
            id="or_list_child",
        ),
        # A condition key makes it a long form condition, a shorthand key is
        # then not allowed
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": "state", "or": [_STATE_CONDITION]}],
            {
                ((0, "entity_id"), *_STATE_REQUIRED),
                (
                    (0, "or"),
                    "not a valid option, did you mean 'for'?",
                    "extra_keys_not_allowed",
                ),
                ((0, "state"), *_STATE_REQUIRED),
            },
            id="state_condition_with_or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": "or", "or": [_STATE_CONDITION]}],
            {
                ((0, "conditions"), *_STATE_REQUIRED),
                ((0, "or"), *_NOT_AN_OPTION),
            },
            id="or_condition_with_or",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": None, "or": [_STATE_CONDITION]}],
            {((0,), *_UNEXPECTED_CONDITION_NONE)},
            id="none_condition_with_or",
        ),
        # A conditions key makes it a long form condition as well
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [_STATE_CONDITION], "conditions": [_STATE_CONDITION]}],
            {((0,), *_UNEXPECTED_CONDITION_NONE)},
            id="or_with_conditions",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": [_STATE_CONDITION], "conditions": [_STATE_CONDITION]}],
            {((0,), *_UNEXPECTED_CONDITION_LIST)},
            id="list_with_conditions",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            ["{{ bad"],
            {((0,), *_EXPECTED_DICT)},
            id="invalid_template",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"foo": 1}],
            {((0,), *_UNEXPECTED_CONDITION_NONE)},
            id="unknown_key",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [5],
            {((0,), *_EXPECTED_DICT)},
            id="not_a_condition",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"or": [_INVALID_TEMPLATE_CONDITION, _UNKNOWN_CONDITION]}],
            {((0, "or", 0, "value_template"), *_INVALID_TEMPLATE)},
            id="or_invalid_template",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"and": [_INVALID_TEMPLATE_CONDITION, _UNKNOWN_CONDITION]}],
            {((0, "and", 0, "value_template"), *_INVALID_TEMPLATE)},
            id="and_invalid_template",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"not": [_INVALID_TEMPLATE_CONDITION, _UNKNOWN_CONDITION]}],
            {((0, "not", 0, "value_template"), *_INVALID_TEMPLATE)},
            id="not_invalid_template",
        ),
        pytest.param(
            cv.CONDITIONS_SCHEMA,
            [{"condition": [_INVALID_TEMPLATE_CONDITION, _UNKNOWN_CONDITION]}],
            {((0, "condition", 0, "value_template"), *_INVALID_TEMPLATE)},
            id="list_invalid_template",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"or": [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE]}],
            {((0, "or", 1, "state"), *_STATE_REQUIRED)},
            id="action_or",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"condition": [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE]}],
            {((0, "condition", 1, "state"), *_STATE_REQUIRED)},
            id="action_list",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"or": [_INVALID_TEMPLATE_CONDITION, _UNKNOWN_CONDITION]}],
            {((0, "or", 0, "value_template"), *_INVALID_TEMPLATE)},
            id="action_or_invalid_template",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"if": [{"or": [_INVALID_TEMPLATE_CONDITION]}], "then": []}],
            {((0, "if", 0, "or", 0, "value_template"), *_INVALID_TEMPLATE)},
            id="action_if_or_invalid_template",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"or": [_STATE_CONDITION], "bogus": 1}],
            {((0, "bogus"), *_NOT_AN_OPTION)},
            id="action_or_extra_key",
        ),
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"condition": "state", "or": [_STATE_CONDITION]}],
            {
                ((0, "entity_id"), *_STATE_REQUIRED),
                (
                    (0, "or"),
                    "not a valid option, did you mean 'for'?",
                    "extra_keys_not_allowed",
                ),
                ((0, "state"), *_STATE_REQUIRED),
            },
            id="action_state_condition_with_or",
        ),
        # Another action key decides the action, the shorthand key is not allowed
        pytest.param(
            cv.SCRIPT_SCHEMA,
            [{"or": [_STATE_CONDITION], "delay": 1}],
            {((0, "or"), *_NOT_AN_OPTION)},
            id="action_delay_with_or",
        ),
    ],
)
@pytest.mark.usefixtures("hass")
def test_condition_shorthand_invalid(
    schema: Callable[[Any], Any],
    config: Any,
    expected_errors: set[tuple[tuple[str | int, ...], str, str | None]],
) -> None:
    """Test an invalid condition shorthand reports the path of the failing child."""
    with pytest.raises(probatio.MultipleInvalid) as excinfo:
        schema(config)

    assert {
        (tuple(error.path), error.error_message, error.code)
        for error in excinfo.value.errors
    } == expected_errors


_CONDITION_SHORTHANDS = [
    pytest.param("and", "and", id="and"),
    pytest.param("or", "or", id="or"),
    pytest.param("not", "not", id="not"),
    pytest.param("condition", "and", id="list"),
]
# A single condition which is not in a list is not a list shorthand
_CONDITION_KEY_SHORTHANDS = _CONDITION_SHORTHANDS[:3]
_CONDITION_SCHEMAS = [
    pytest.param(cv.CONDITION_SCHEMA, id="condition"),
    pytest.param(cv.CONDITION_ACTION_SCHEMA, id="action"),
]


def _validation_errors(
    schema: Callable[[Any], Any], config: dict[str, Any], children_key: str
) -> set[tuple[tuple[str | int, ...], str, str | None]]:
    """Return the validation errors, with the children at the conditions key."""
    with pytest.raises(probatio.MultipleInvalid) as excinfo:
        schema(config)

    renamed = {children_key: "conditions"}
    return {
        (
            (*(renamed.get(key, key) for key in error.path[:1]), *error.path[1:]),
            error.error_message,
            error.code,
        )
        for error in excinfo.value.errors
    }


@pytest.mark.parametrize("schema", _CONDITION_SCHEMAS)
@pytest.mark.parametrize(
    ("shorthand_key", "condition", "children", "options"),
    [
        pytest.param(*shorthand.values, children, options, id=f"{shorthand.id}-{id_}")
        for shorthands, children, options, id_ in (
            (_CONDITION_KEY_SHORTHANDS, _STATE_CONDITION, {}, "single_child"),
            (_CONDITION_KEY_SHORTHANDS, None, {}, "no_children"),
            (_CONDITION_SHORTHANDS, [], {}, "empty"),
            (
                _CONDITION_SHORTHANDS,
                [
                    _STATE_CONDITION,
                    {"condition": "template", "value_template": "{{ 1 }}"},
                ],
                {},
                "children",
            ),
            (
                _CONDITION_SHORTHANDS,
                [{"or": [_STATE_CONDITION, {"condition": [_STATE_CONDITION]}]}],
                {},
                "nested_shorthand",
            ),
            (
                _CONDITION_SHORTHANDS,
                [_STATE_CONDITION],
                {"alias": "x", "enabled": False},
                "alias_enabled",
            ),
            (
                _CONDITION_SHORTHANDS,
                [_STATE_CONDITION],
                {"enabled": "{{ 1 }}"},
                "enabled_template",
            ),
            (_CONDITION_SHORTHANDS, [_STATE_CONDITION], {"note": "x"}, "note"),
        )
        for shorthand in shorthands
    ],
)
@pytest.mark.usefixtures("hass")
def test_condition_shorthand_same_as_long_form(
    schema: Callable[[Any], Any],
    shorthand_key: str,
    condition: str,
    children: Any,
    options: dict[str, Any],
) -> None:
    """Test a condition shorthand gives the same result as the long form."""
    validated = schema({shorthand_key: children, **options})

    assert validated == schema(
        {"condition": condition, "conditions": children, **options}
    )
    assert validated["condition"] == condition


@pytest.mark.parametrize("schema", _CONDITION_SCHEMAS)
@pytest.mark.parametrize(
    ("shorthand_key", "condition", "children", "options"),
    [
        pytest.param(*shorthand.values, children, options, id=f"{shorthand.id}-{id_}")
        for shorthands, children, options, id_ in (
            (
                _CONDITION_KEY_SHORTHANDS,
                _STATE_CONDITION_WITHOUT_STATE,
                {},
                "invalid_single_child",
            ),
            (_CONDITION_KEY_SHORTHANDS, 5, {}, "single_child_not_a_mapping"),
            (
                _CONDITION_SHORTHANDS,
                [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE],
                {},
                "invalid_child",
            ),
            (
                _CONDITION_SHORTHANDS,
                [_INVALID_TEMPLATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE],
                {},
                "invalid_children",
            ),
            (
                _CONDITION_SHORTHANDS,
                [_STATE_CONDITION, 5],
                {},
                "child_not_a_mapping",
            ),
            (
                _CONDITION_SHORTHANDS,
                [{"or": [_STATE_CONDITION, _STATE_CONDITION_WITHOUT_STATE]}],
                {},
                "invalid_nested_shorthand",
            ),
            (_CONDITION_SHORTHANDS, [_STATE_CONDITION], {"bogus": 1}, "extra_key"),
            (_CONDITION_SHORTHANDS, [_STATE_CONDITION], {"alias": {}}, "alias"),
            (_CONDITION_SHORTHANDS, [_STATE_CONDITION], {"enabled": {}}, "enabled"),
        )
        for shorthand in shorthands
    ],
)
@pytest.mark.usefixtures("hass")
def test_condition_shorthand_invalid_same_as_long_form(
    schema: Callable[[Any], Any],
    shorthand_key: str,
    condition: str,
    children: Any,
    options: dict[str, Any],
) -> None:
    """Test an invalid condition shorthand gives the same errors as the long form."""
    assert _validation_errors(
        schema, {shorthand_key: children, **options}, shorthand_key
    ) == _validation_errors(
        schema,
        {"condition": condition, "conditions": children, **options},
        "conditions",
    )


def test_whitespace() -> None:
    """Test whitespace validation."""
    schema = probatio.Schema(cv.whitespace)

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
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("  ", "   "):
        assert schema(value)


def test_currency() -> None:
    """Test currency validator."""
    schema = probatio.Schema(cv.currency)

    for value in (
        None,
        "BTC",
    ):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("EUR", "USD"):
        assert schema(value)


def test_historic_currency() -> None:
    """Test historic currency validator."""
    schema = probatio.Schema(cv.historic_currency)

    for value in (None, "BTC", "EUR"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("DEM", "NLG"):
        assert schema(value)


def test_country() -> None:
    """Test country validator."""
    schema = probatio.Schema(cv.country)

    for value in (None, "Candyland", "USA"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("NL", "SE"):
        assert schema(value)


def test_language() -> None:
    """Test language validator."""
    schema = probatio.Schema(cv.language)

    for value in (None, "Klingon", "english"):
        with pytest.raises(probatio.MultipleInvalid):
            schema(value)

    for value in ("en", "sv"):
        assert schema(value)


@pytest.mark.usefixtures("hass")
def test_positive_time_period_template() -> None:
    """Test positive time period template validation."""
    schema = probatio.Schema(cv.positive_time_period_template)

    with pytest.raises(probatio.MultipleInvalid):
        schema({})
    with pytest.raises(probatio.MultipleInvalid):
        schema({5: 5})
    with pytest.raises(probatio.MultipleInvalid):
        schema({"invalid": 5})
    with pytest.raises(probatio.MultipleInvalid):
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
    with pytest.raises(probatio.Invalid):
        cv.domain_key(5)
    with pytest.raises(probatio.Invalid):
        cv.domain_key("")
    with pytest.raises(probatio.Invalid):
        cv.domain_key("hue ")
    with pytest.raises(probatio.Invalid):
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
    with pytest.raises(probatio.Invalid, match=msg):
        cv.color_hex("#777")

    with pytest.raises(probatio.Invalid, match=msg):
        cv.color_hex("FFFFF")

    with pytest.raises(probatio.Invalid, match=msg):
        cv.color_hex("FFFFFF")

    with pytest.raises(probatio.Invalid, match=msg):
        cv.color_hex("#FFFFFFF")

    with pytest.raises(probatio.Invalid, match=msg):
        cv.color_hex("#FFFFFF\n")

    with pytest.raises(probatio.Invalid, match=msg):
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
        await cv.async_validate(hass, probatio.All(cv.isdir, cv.string), tmpdir)
        assert validator_calls == {"isdir": [hass.loop_thread_id, ANY], "string": [ANY]}
        assert validator_calls["isdir"][1] != hass.loop_thread_id
        assert validator_calls["string"][0] != hass.loop_thread_id
        validator_calls = {}

        # Assert validation in executor when decorated with not_async_friendly
        await cv.async_validate(hass, probatio.All(cv.string, cv.isdir), tmpdir)
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
        probatio.All(cv.isdir, cv.string)(tmpdir)
        assert validator_calls == {
            "isdir": [hass.loop_thread_id],
            "string": [hass.loop_thread_id],
        }
        validator_calls = {}

        # Assert validation in event loop when not using cv.async_validate
        probatio.All(cv.string, cv.isdir)(tmpdir)
        assert validator_calls == {
            "isdir": [hass.loop_thread_id],
            "string": [hass.loop_thread_id],
        }
        validator_calls = {}


async def test_nested_trigger_list() -> None:
    """Test triggers within nested lists are flattened."""

    trigger_config = [
        {
            "triggers": {
                "platform": "event",
                "event_type": "trigger_1",
            },
        },
        {
            "platform": "event",
            "event_type": "trigger_2",
        },
        {"triggers": []},
        {"triggers": None},
        {
            "triggers": [
                {
                    "platform": "event",
                    "event_type": "trigger_3",
                },
                {
                    "trigger": "event",
                    "event_type": "trigger_4",
                },
            ],
        },
    ]

    validated_triggers = TRIGGER_SCHEMA(trigger_config)

    assert validated_triggers == [
        {
            "platform": "event",
            "event_type": "trigger_1",
        },
        {
            "platform": "event",
            "event_type": "trigger_2",
        },
        {
            "platform": "event",
            "event_type": "trigger_3",
        },
        {
            "platform": "event",
            "event_type": "trigger_4",
        },
    ]


async def test_nested_trigger_list_extra() -> None:
    """Test triggers key with extra keys is not modified."""

    trigger_config = [
        {
            "platform": "other",
            "triggers": [
                {
                    "platform": "event",
                    "event_type": "trigger_1",
                },
                {
                    "platform": "event",
                    "event_type": "trigger_2",
                },
            ],
        },
    ]

    validated_triggers = TRIGGER_SCHEMA(trigger_config)

    assert validated_triggers == [
        {
            "platform": "other",
            "triggers": [
                {
                    "platform": "event",
                    "event_type": "trigger_1",
                },
                {
                    "platform": "event",
                    "event_type": "trigger_2",
                },
            ],
        },
    ]


_VALID_TRIGGER = {"trigger": "event", "event_type": "x"}
_VALIDATED_TRIGGER = {"platform": "event", "event_type": "x"}


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(None, [], id="none"),
        pytest.param([], [], id="empty"),
        pytest.param(_VALID_TRIGGER, [_VALIDATED_TRIGGER], id="single"),
        pytest.param(
            [{"platform": "event", "event_type": "x"}],
            [_VALIDATED_TRIGGER],
            id="platform_key",
        ),
        pytest.param(
            [
                {"triggers": [_VALID_TRIGGER, _VALID_TRIGGER]},
                _VALID_TRIGGER,
                {"triggers": _VALID_TRIGGER},
            ],
            [_VALIDATED_TRIGGER] * 4,
            id="sublists",
        ),
        pytest.param(
            {"triggers": [_VALID_TRIGGER, _VALID_TRIGGER]},
            [_VALIDATED_TRIGGER] * 2,
            id="single_sublist",
        ),
        pytest.param({"triggers": None}, [], id="single_sublist_none"),
        pytest.param([{"triggers": []}], [], id="sublist_empty"),
        pytest.param([{"triggers": None}], [], id="sublist_none"),
    ],
)
def test_trigger_schema_valid(config: Any, expected: list[dict[str, Any]]) -> None:
    """Test the validated output of the trigger schema."""
    assert TRIGGER_SCHEMA(config) == expected


@pytest.mark.parametrize(
    ("config", "expected_errors"),
    [
        pytest.param(
            _INVALID_TRIGGER, [(["alias"], "expected str", "type")], id="single"
        ),
        pytest.param(
            [_VALID_TRIGGER, _INVALID_TRIGGER],
            [([1, "alias"], "expected str", "type")],
            id="list",
        ),
        pytest.param(
            [{"triggers": [_VALID_TRIGGER, _VALID_TRIGGER]}, _INVALID_TRIGGER],
            [([1, "alias"], "expected str", "type")],
            id="after_sublist",
        ),
        pytest.param(
            [_VALID_TRIGGER, {"triggers": [_VALID_TRIGGER, _INVALID_TRIGGER]}],
            [([1, "triggers", 1, "alias"], "expected str", "type")],
            id="in_sublist",
        ),
        pytest.param(
            [{"triggers": _INVALID_TRIGGER}],
            [([0, "triggers", "alias"], "expected str", "type")],
            id="sublist_single",
        ),
        pytest.param(
            {"triggers": [_VALID_TRIGGER, _INVALID_TRIGGER]},
            [(["triggers", 1, "alias"], "expected str", "type")],
            id="single_sublist",
        ),
        pytest.param(
            {"triggers": _INVALID_TRIGGER},
            [(["triggers", "alias"], "expected str", "type")],
            id="single_sublist_single",
        ),
        pytest.param(
            [{"triggers": [{"triggers": [_VALID_TRIGGER]}]}],
            [([0, "triggers", 0, "trigger"], "required key not provided", "required")],
            id="sublist_in_sublist",
        ),
        pytest.param(
            [{"triggers": [_VALID_TRIGGER], "alias": "x"}],
            [([0, "trigger"], "required key not provided", "required")],
            id="sublist_extra_key",
        ),
        pytest.param(
            [{"triggers": [5]}],
            [([0, "triggers", 0], "expected a mapping", "not_a_dictionary")],
            id="sublist_non_dict_item",
        ),
        pytest.param(
            [{"triggers": 5}],
            [([0, "triggers"], "expected a mapping", "not_a_dictionary")],
            id="sublist_non_dict",
        ),
        pytest.param(
            5, [([], "expected a mapping", "not_a_dictionary")], id="non_dict"
        ),
        pytest.param(
            [5], [([0], "expected a mapping", "not_a_dictionary")], id="non_dict_item"
        ),
        pytest.param(
            [None], [([0], "expected a mapping", "not_a_dictionary")], id="none_item"
        ),
        pytest.param(
            [["triggers"]],
            [([0], "expected a mapping", "not_a_dictionary")],
            id="list_item",
        ),
        pytest.param(
            ["triggers"],
            [([0], "expected a mapping", "not_a_dictionary")],
            id="string_item",
        ),
        pytest.param(
            [{"event_type": "x"}],
            [([0, "trigger"], "required key not provided", "required")],
            id="missing_trigger",
        ),
        pytest.param(
            [{"trigger": 5}],
            [([0, "platform"], "expected str", "type")],
            id="trigger_not_string",
        ),
        pytest.param(
            [{"trigger": "event", "platform": "event"}],
            [
                (
                    [0],
                    "Cannot specify both 'platform' and 'trigger'."
                    " Please use 'trigger' only.",
                    None,
                )
            ],
            id="trigger_and_platform",
        ),
        pytest.param(
            [
                _INVALID_TRIGGER,
                {"triggers": [_INVALID_TRIGGER, {"event_type": "x"}]},
                5,
            ],
            [
                ([0, "alias"], "expected str", "type"),
                ([1, "triggers", 0, "alias"], "expected str", "type"),
                (
                    [1, "triggers", 1, "trigger"],
                    "required key not provided",
                    "required",
                ),
                ([2], "expected a mapping", "not_a_dictionary"),
            ],
            id="several_errors",
        ),
    ],
)
def test_trigger_schema_invalid(
    config: Any, expected_errors: list[tuple[list[str | int], str, str | None]]
) -> None:
    """Test the errors of the trigger schema index the config as written."""
    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        TRIGGER_SCHEMA(config)

    assert [
        (err.path, err.error_message, err.code) for err in exc_info.value.errors
    ] == expected_errors


async def test_trigger_backwards_compatibility() -> None:
    """Test triggers with backwards compatibility."""

    assert cv._trigger_pre_validator("str") == "str"
    assert cv._trigger_pre_validator({"platform": "abc"}) == {"platform": "abc"}
    assert cv._trigger_pre_validator({"trigger": "abc"}) == {"platform": "abc"}
    with pytest.raises(
        probatio.Invalid,
        match=(
            "Cannot specify both 'platform' and 'trigger'. Please use 'trigger' only."
        ),
    ):
        cv._trigger_pre_validator({"trigger": "abc", "platform": "def"})
    with pytest.raises(
        probatio.Invalid,
        match=re.escape("required key not provided at 'trigger'"),
    ):
        cv._trigger_pre_validator({})


async def test_is_entity_service_schema(
    hass: HomeAssistant,
) -> None:
    """Test cv.is_entity_service_schema."""
    for schema in (
        probatio.Schema({"some": str}),
        probatio.All(probatio.Schema({"some": str})),
        probatio.Any(probatio.Schema({"some": str})),
        probatio.Any(cv.make_entity_service_schema({"some": str})),
    ):
        assert cv.is_entity_service_schema(schema) is False

    for schema in (
        cv.make_entity_service_schema({"some": str}),
        probatio.Schema(cv.make_entity_service_schema({"some": str})),
        probatio.Schema(probatio.All(cv.make_entity_service_schema({"some": str}))),
        probatio.Schema(probatio.Schema(cv.make_entity_service_schema({"some": str}))),
        probatio.All(cv.make_entity_service_schema({"some": str})),
        probatio.All(probatio.All(cv.make_entity_service_schema({"some": str}))),
        probatio.All(probatio.Schema(cv.make_entity_service_schema({"some": str}))),
    ):
        assert cv.is_entity_service_schema(schema) is True


def test_renamed(caplog: pytest.LogCaptureFixture, schema) -> None:
    """Test renamed."""
    renamed_schema = probatio.All(cv.renamed("mors", "mars"), schema)

    test_data = {"mars": True}
    output = renamed_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert output == test_data

    test_data = {"mors": True}
    output = renamed_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert output == {"mars": True}

    test_data = {"mars": True, "mors": True}
    with pytest.raises(
        probatio.Invalid,
        match="Cannot specify both 'mors' and 'mars'. Please use 'mars' only.",
    ):
        renamed_schema(test_data.copy())
    assert len(caplog.records) == 0

    # Check error handling if data is not a dict
    with pytest.raises(probatio.Invalid, match="expected a mapping"):
        renamed_schema([])


def test_stop_action_schema_error_false_with_response() -> None:
    """Test stop action allows error: false with response_variable."""
    schema = cv._SCRIPT_STOP_SCHEMA

    # error: true with response_variable should fail
    with pytest.raises(probatio.Invalid, match="not allowed to add a response"):
        schema({"stop": "Error", "error": True, "response_variable": "result"})

    # error: false with response_variable should work
    config = schema({"stop": "Done", "error": False, "response_variable": "result"})
    assert config["error"] is False
    assert config["response_variable"] == "result"

    # no error with response_variable should work
    config = schema({"stop": "Done", "response_variable": "result"})
    assert config["response_variable"] == "result"


_NOTE_SCHEMA_PARAMS = [
    pytest.param(
        cv.TRIGGER_BASE_SCHEMA,
        {"platform": "event"},
        id="trigger_base",
    ),
    pytest.param(
        cv.CONDITION_SCHEMA,
        {"condition": "state", "entity_id": "sun.sun", "state": "above_horizon"},
        id="condition",
    ),
    pytest.param(
        cv.script_action,
        {"action": "test.foo"},
        id="script_action",
    ),
]


@pytest.mark.parametrize(("validator", "base_config"), _NOTE_SCHEMA_PARAMS)
@pytest.mark.usefixtures("hass")
def test_base_schemas_accept_note(
    validator: Callable[[dict[str, Any]], dict[str, Any]],
    base_config: dict[str, Any],
) -> None:
    """Test that the note field is accepted and stripped from the output."""
    validated = validator({**base_config, "note": "Single line"})
    assert "note" not in validated


@pytest.mark.parametrize(("validator", "base_config"), _NOTE_SCHEMA_PARAMS)
@pytest.mark.parametrize(
    "invalid_note",
    [
        pytest.param(None, id="none"),
        pytest.param(42, id="int"),
        pytest.param(True, id="bool"),
        pytest.param([], id="list"),
        pytest.param({}, id="dict"),
    ],
)
@pytest.mark.usefixtures("hass")
def test_base_schemas_reject_invalid_note(
    validator: Callable[[dict[str, Any]], dict[str, Any]],
    base_config: dict[str, Any],
    invalid_note: Any,
) -> None:
    """Test that script, condition, trigger base schemas reject non-string notes."""
    with pytest.raises(probatio.Invalid):
        validator({**base_config, "note": invalid_note})


_CHOOSE_OPTION_BASE_CONFIG = {
    "conditions": [
        {"condition": "state", "entity_id": "sun.sun", "state": "above_horizon"}
    ],
    "sequence": [{"action": "test.foo"}],
}


@pytest.mark.usefixtures("hass")
def test_choose_option_accepts_note() -> None:
    """Test that the note field is accepted and stripped from a choose option."""
    validated = cv.script_action(
        {"choose": [{**_CHOOSE_OPTION_BASE_CONFIG, "note": "Single line"}]}
    )
    assert "note" not in validated["choose"][0]


@pytest.mark.parametrize(
    "invalid_note",
    [
        pytest.param(None, id="none"),
        pytest.param(42, id="int"),
        pytest.param(True, id="bool"),
        pytest.param([], id="list"),
        pytest.param({}, id="dict"),
    ],
)
@pytest.mark.usefixtures("hass")
def test_choose_option_rejects_invalid_note(invalid_note: Any) -> None:
    """Test that choose option schemas reject non-string notes."""
    with pytest.raises(probatio.Invalid):
        cv.script_action(
            {"choose": [{**_CHOOSE_OPTION_BASE_CONFIG, "note": invalid_note}]}
        )
