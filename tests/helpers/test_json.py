"""Test Home Assistant remote methods and classes."""
import datetime
from functools import partial
import json
import math
import os
from pathlib import Path
import time
from typing import NamedTuple
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers.json import (
    ExtendedJSONEncoder,
    JSONEncoder as DefaultHASSJSONEncoder,
    find_paths_unserializable_data,
    json_bytes_strip_null,
    json_dumps,
    json_dumps_sorted,
    save_json,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.color import RGBColor
from homeassistant.util.json import SerializationError, load_json

# Test data that can be saved as JSON
TEST_JSON_A = {"a": 1, "B": "two"}
TEST_JSON_B = {"a": "one", "B": 2}


@pytest.mark.parametrize("encoder", (DefaultHASSJSONEncoder, ExtendedJSONEncoder))
def test_json_encoder(hass: HomeAssistant, encoder: type[json.JSONEncoder]) -> None:
    """Test the JSON encoders."""
    ha_json_enc = encoder()
    state = State("test.test", "hello")

    # Test serializing a datetime
    now = dt_util.utcnow()
    assert ha_json_enc.default(now) == now.isoformat()

    # Test serializing a set()
    data = {"milk", "beer"}
    assert sorted(ha_json_enc.default(data)) == sorted(data)

    # Test serializing an object which implements as_dict
    assert ha_json_enc.default(state) == state.as_dict()


def test_json_encoder_raises(hass: HomeAssistant) -> None:
    """Test the JSON encoder raises on unsupported types."""
    ha_json_enc = DefaultHASSJSONEncoder()

    # Default method raises TypeError if non HA object
    with pytest.raises(TypeError):
        ha_json_enc.default(1)


def test_extended_json_encoder(hass: HomeAssistant) -> None:
    """Test the extended JSON encoder."""
    ha_json_enc = ExtendedJSONEncoder()
    # Test serializing a timedelta
    data = datetime.timedelta(
        days=50,
        seconds=27,
        microseconds=10,
        milliseconds=29000,
        minutes=5,
        hours=8,
        weeks=2,
    )
    assert ha_json_enc.default(data) == {
        "__type": str(type(data)),
        "total_seconds": data.total_seconds(),
    }

    # Test serializing a time
    o = datetime.time(7, 20)
    assert ha_json_enc.default(o) == {"__type": str(type(o)), "isoformat": "07:20:00"}

    # Test serializing a date
    o = datetime.date(2021, 12, 24)
    assert ha_json_enc.default(o) == {"__type": str(type(o)), "isoformat": "2021-12-24"}

    # Default method falls back to repr(o)
    o = object()
    assert ha_json_enc.default(o) == {"__type": str(type(o)), "repr": repr(o)}


def test_json_dumps_sorted() -> None:
    """Test the json dumps sorted function."""
    data = {"c": 3, "a": 1, "b": 2}
    assert json_dumps_sorted(data) == json.dumps(
        data, sort_keys=True, separators=(",", ":")
    )


def test_json_dumps_float_subclass() -> None:
    """Test the json dumps a float subclass."""

    class FloatSubclass(float):
        """A float subclass."""

    assert json_dumps({"c": FloatSubclass(1.2)}) == '{"c":1.2}'


def test_json_dumps_tuple_subclass() -> None:
    """Test the json dumps a tuple subclass."""

    tt = time.struct_time((1999, 3, 17, 32, 44, 55, 2, 76, 0))

    assert json_dumps(tt) == "[1999,3,17,32,44,55,2,76,0]"


def test_json_dumps_named_tuple_subclass() -> None:
    """Test the json dumps a tuple subclass."""

    class NamedTupleSubclass(NamedTuple):
        """A NamedTuple subclass."""

        name: str

    nts = NamedTupleSubclass("a")

    assert json_dumps(nts) == '["a"]'


def test_json_dumps_rgb_color_subclass() -> None:
    """Test the json dumps of RGBColor."""
    rgb = RGBColor(4, 2, 1)

    assert json_dumps(rgb) == "[4,2,1]"


def test_json_bytes_strip_null() -> None:
    """Test stripping nul from strings."""

    assert json_bytes_strip_null("\0") == b'""'
    assert json_bytes_strip_null("silly\0stuff") == b'"silly"'
    assert json_bytes_strip_null(["one", "two\0", "three"]) == b'["one","two","three"]'
    assert (
        json_bytes_strip_null({"k1": "one", "k2": "two\0", "k3": "three"})
        == b'{"k1":"one","k2":"two","k3":"three"}'
    )
    assert (
        json_bytes_strip_null([[{"k1": {"k2": ["silly\0stuff"]}}]])
        == b'[[{"k1":{"k2":["silly"]}}]]'
    )


def test_save_and_load(tmp_path: Path) -> None:
    """Test saving and loading back."""
    fname = tmp_path / "test1.json"
    save_json(fname, TEST_JSON_A)
    data = load_json(fname)
    assert data == TEST_JSON_A


def test_save_and_load_int_keys(tmp_path: Path) -> None:
    """Test saving and loading back stringifies the keys."""
    fname = tmp_path / "test1.json"
    save_json(fname, {1: "a", 2: "b"})
    data = load_json(fname)
    assert data == {"1": "a", "2": "b"}


def test_save_and_load_private(tmp_path: Path) -> None:
    """Test we can load private files and that they are protected."""
    fname = tmp_path / "test2.json"
    save_json(fname, TEST_JSON_A, private=True)
    data = load_json(fname)
    assert data == TEST_JSON_A
    stats = os.stat(fname)
    assert stats.st_mode & 0o77 == 0


@pytest.mark.parametrize("atomic_writes", [True, False])
def test_overwrite_and_reload(atomic_writes: bool, tmp_path: Path) -> None:
    """Test that we can overwrite an existing file and read back."""
    fname = tmp_path / "test3.json"
    save_json(fname, TEST_JSON_A, atomic_writes=atomic_writes)
    save_json(fname, TEST_JSON_B, atomic_writes=atomic_writes)
    data = load_json(fname)
    assert data == TEST_JSON_B


def test_save_bad_data() -> None:
    """Test error from trying to save unserializable data."""

    class CannotSerializeMe:
        """Cannot serialize this."""

    with pytest.raises(SerializationError) as excinfo:
        save_json("test4", {"hello": CannotSerializeMe()})

    assert "Failed to serialize to JSON: test4. Bad data at $.hello=" in str(
        excinfo.value
    )


def test_custom_encoder(tmp_path: Path) -> None:
    """Test serializing with a custom encoder."""

    class MockJSONEncoder(json.JSONEncoder):
        """Mock JSON encoder."""

        def default(self, o):
            """Mock JSON encode method."""
            return "9"

    fname = tmp_path / "test6.json"
    save_json(fname, Mock(), encoder=MockJSONEncoder)
    data = load_json(fname)
    assert data == "9"


def test_saving_subclassed_datetime(tmp_path: Path) -> None:
    """Test saving subclassed datetime objects."""

    class SubClassDateTime(datetime.datetime):
        """Subclass datetime."""

    time = SubClassDateTime.fromtimestamp(0)

    fname = tmp_path / "test6.json"
    save_json(fname, {"time": time})
    data = load_json(fname)
    assert data == {"time": time.isoformat()}


def test_default_encoder_is_passed(tmp_path: Path) -> None:
    """Test we use orjson if they pass in the default encoder."""
    fname = tmp_path / "test6.json"
    with patch(
        "homeassistant.helpers.json.orjson.dumps", return_value=b"{}"
    ) as mock_orjson_dumps:
        save_json(fname, {"any": 1}, encoder=DefaultHASSJSONEncoder)
    assert len(mock_orjson_dumps.mock_calls) == 1
    # Patch json.dumps to make sure we are using the orjson path
    with patch("homeassistant.helpers.json.json.dumps", side_effect=Exception):
        save_json(fname, {"any": {1}}, encoder=DefaultHASSJSONEncoder)
    data = load_json(fname)
    assert data == {"any": [1]}


def test_find_unserializable_data() -> None:
    """Find unserializeable data."""
    assert find_paths_unserializable_data(1) == {}
    assert find_paths_unserializable_data([1, 2]) == {}
    assert find_paths_unserializable_data({"something": "yo"}) == {}

    assert find_paths_unserializable_data({"something": set()}) == {
        "$.something": set()
    }
    assert find_paths_unserializable_data({"something": [1, set()]}) == {
        "$.something[1]": set()
    }
    assert find_paths_unserializable_data([1, {"bla": set(), "blub": set()}]) == {
        "$[1].bla": set(),
        "$[1].blub": set(),
    }
    assert find_paths_unserializable_data({("A",): 1}) == {"$<key: ('A',)>": ("A",)}
    assert math.isnan(
        find_paths_unserializable_data(
            float("nan"), dump=partial(json.dumps, allow_nan=False)
        )["$"]
    )

    # Test custom encoder + State support.

    class MockJSONEncoder(json.JSONEncoder):
        """Mock JSON encoder."""

        def default(self, o):
            """Mock JSON encode method."""
            if isinstance(o, datetime.datetime):
                return o.isoformat()
            return super().default(o)

    bad_data = object()

    assert find_paths_unserializable_data(
        [State("mock_domain.mock_entity", "on", {"bad": bad_data})],
        dump=partial(json.dumps, cls=MockJSONEncoder),
    ) == {"$[0](State: mock_domain.mock_entity).attributes.bad": bad_data}

    assert find_paths_unserializable_data(
        [Event("bad_event", {"bad_attribute": bad_data})],
        dump=partial(json.dumps, cls=MockJSONEncoder),
    ) == {"$[0](Event: bad_event).data.bad_attribute": bad_data}

    class BadData:
        def __init__(self):
            self.bla = bad_data

        def as_dict(self):
            return {"bla": self.bla}

    assert find_paths_unserializable_data(
        BadData(),
        dump=partial(json.dumps, cls=MockJSONEncoder),
    ) == {"$(BadData).bla": bad_data}
