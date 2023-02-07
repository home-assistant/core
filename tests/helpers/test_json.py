"""Test Home Assistant remote methods and classes."""
import datetime
import json
import time
from typing import NamedTuple

import pytest

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.json import (
    ExtendedJSONEncoder,
    JSONEncoder,
    json_bytes_strip_null,
    json_dumps,
    json_dumps_sorted,
    json_loads_object,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.color import RGBColor


@pytest.mark.parametrize("encoder", (JSONEncoder, ExtendedJSONEncoder))
def test_json_encoder(hass, encoder):
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
    ha_json_enc = JSONEncoder()

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


def test_json_loads_object():
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
