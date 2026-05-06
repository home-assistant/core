"""Test serialization functions for Home Assistant templates."""

from __future__ import annotations

import json

import orjson
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError

from tests.helpers.template.helpers import render, render_to_info


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


def test_from_hex(hass: HomeAssistant) -> None:
    """Test the fromhex filter."""
    assert render(hass, "{{ '0F010003' | from_hex }}") == b"\x0f\x01\x00\x03"


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
