"""Test Home Assistant json utility functions."""
from pathlib import Path

import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import (
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
    """Test error from trying to load unserialisable data."""
    fname = tmp_path / "test5.json"
    with open(fname, "w") as fh:
        fh.write(TEST_BAD_SERIALIED)
    with pytest.raises(HomeAssistantError) as err:
        load_json(fname)
    assert isinstance(err.value.__cause__, ValueError)


def test_load_json_os_error() -> None:
    """Test trying to load JSON data from a directory."""
    fname = "/"
    with pytest.raises(HomeAssistantError) as err:
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


async def test_deprecated_test_find_unserializable_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deprecated test_find_unserializable_data logs a warning."""
    # pylint: disable-next=hass-deprecated-import,import-outside-toplevel
    from homeassistant.util.json import find_paths_unserializable_data

    find_paths_unserializable_data(1)
    assert (
        "uses find_paths_unserializable_data from homeassistant.util.json"
        in caplog.text
    )
    assert "should be updated to use homeassistant.helpers.json module" in caplog.text


async def test_deprecated_save_json(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test deprecated save_json logs a warning."""
    # pylint: disable-next=hass-deprecated-import,import-outside-toplevel
    from homeassistant.util.json import save_json

    fname = tmp_path / "test1.json"
    save_json(fname, TEST_JSON_A)
    assert "uses save_json from homeassistant.util.json" in caplog.text
    assert "should be updated to use homeassistant.helpers.json module" in caplog.text
