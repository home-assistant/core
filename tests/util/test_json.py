"""Test Home Assistant json utility functions."""

from pathlib import Path
import re

import orjson
import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import (
    json_loads,
    json_loads_array,
    json_loads_object,
    load_json,
    load_json_array,
    load_json_object,
)

# Test data that can be saved as JSON
TEST_JSON_A = {"a": 1, "B": "two"}
# Test data that cannot be loaded as JSON
TEST_BAD_SERIALIED = "THIS IS NOT JSON\n"


def test_load_bad_data(tmp_path: Path) -> None:
    """Test error from trying to load unserializable data."""
    fname = tmp_path / "test5.json"
    with open(fname, "w", encoding="utf8") as fh:
        fh.write(TEST_BAD_SERIALIED)
    with pytest.raises(HomeAssistantError, match=re.escape(str(fname))) as err:
        load_json(fname)
    assert isinstance(err.value.__cause__, ValueError)


def test_load_json_os_error() -> None:
    """Test trying to load JSON data from a directory."""
    fname = "/"
    with pytest.raises(HomeAssistantError, match=re.escape(str(fname))) as err:
        load_json(fname)
    assert isinstance(err.value.__cause__, OSError)


def test_load_json_file_not_found_error() -> None:
    """Test trying to load object data from inexistent JSON file."""
    fname = "invalid_file.json"

    assert load_json(fname) == {}
    assert load_json(fname, default="") == ""
    assert load_json_object(fname) == {}
    assert load_json_object(fname, default={"Hi": "Peter"}) == {"Hi": "Peter"}
    assert load_json_array(fname) == []
    assert load_json_array(fname, default=["Hi"]) == ["Hi"]


def test_load_json_value_data(tmp_path: Path) -> None:
    """Test trying to load object data from JSON file."""
    fname = tmp_path / "test5.json"
    with open(fname, "w", encoding="utf8") as handle:
        handle.write('"two"')

    assert load_json(fname) == "two"
    with pytest.raises(
        HomeAssistantError, match="Expected JSON to be parsed as a dict"
    ):
        load_json_object(fname)
    with pytest.raises(
        HomeAssistantError, match="Expected JSON to be parsed as a list"
    ):
        load_json_array(fname)


def test_load_json_object_data(tmp_path: Path) -> None:
    """Test trying to load object data from JSON file."""
    fname = tmp_path / "test5.json"
    with open(fname, "w", encoding="utf8") as handle:
        handle.write('{"a": 1, "B": "two"}')

    assert load_json(fname) == {"a": 1, "B": "two"}
    assert load_json_object(fname) == {"a": 1, "B": "two"}
    with pytest.raises(
        HomeAssistantError, match="Expected JSON to be parsed as a list"
    ):
        load_json_array(fname)


def test_load_json_array_data(tmp_path: Path) -> None:
    """Test trying to load array data from JSON file."""
    fname = tmp_path / "test5.json"
    with open(fname, "w", encoding="utf8") as handle:
        handle.write('[{"a": 1, "B": "two"}]')

    assert load_json(fname) == [{"a": 1, "B": "two"}]
    assert load_json_array(fname) == [{"a": 1, "B": "two"}]
    with pytest.raises(
        HomeAssistantError, match="Expected JSON to be parsed as a dict"
    ):
        load_json_object(fname)


def test_json_loads_array() -> None:
    """Test json_loads_array validates result."""
    assert json_loads_array('[{"c":1.2}]') == [{"c": 1.2}]
    with pytest.raises(
        ValueError, match="Expected JSON to be parsed as a list got <class 'dict'>"
    ):
        json_loads_array("{}")
    with pytest.raises(
        ValueError, match="Expected JSON to be parsed as a list got <class 'bool'>"
    ):
        json_loads_array("true")
    with pytest.raises(
        ValueError, match="Expected JSON to be parsed as a list got <class 'NoneType'>"
    ):
        json_loads_array("null")


def test_json_loads_object() -> None:
    """Test json_loads_object validates result."""
    assert json_loads_object('{"c":1.2}') == {"c": 1.2}
    with pytest.raises(
        ValueError, match="Expected JSON to be parsed as a dict got <class 'list'>"
    ):
        json_loads_object("[]")
    with pytest.raises(
        ValueError, match="Expected JSON to be parsed as a dict got <class 'bool'>"
    ):
        json_loads_object("true")
    with pytest.raises(
        ValueError, match="Expected JSON to be parsed as a dict got <class 'NoneType'>"
    ):
        json_loads_object("null")


async def test_loading_derived_class() -> None:
    """Test loading data from classes derived from str."""

    class MyStr(str):
        __slots__ = ()

    class MyBytes(bytes):
        pass

    assert json_loads('"abc"') == "abc"
    assert json_loads(MyStr('"abc"')) == "abc"

    assert json_loads(b'"abc"') == "abc"
    with pytest.raises(orjson.JSONDecodeError):
        assert json_loads(MyBytes(b'"abc"')) == "abc"
