"""Test Home Assistant remote methods and classes."""
from datetime import timedelta

import pytest

from homeassistant import core
from homeassistant.helpers.json import ExtendedJSONEncoder, JSONEncoder
from homeassistant.util import dt as dt_util


def test_json_encoder(hass):
    """Test the JSON Encoder."""
    ha_json_enc = JSONEncoder()
    state = core.State("test.test", "hello")

    # Test serializing a datetime
    now = dt_util.utcnow()
    assert ha_json_enc.default(now) == now.isoformat()

    # Test serializing a set()
    data = {"milk", "beer"}
    assert sorted(ha_json_enc.default(data)) == sorted(data)

    # Test serializing an object which implements as_dict
    assert ha_json_enc.default(state) == state.as_dict()

    # Default method raises TypeError if non HA object
    with pytest.raises(TypeError):
        ha_json_enc.default(1)


def test_trace_json_encoder(hass):
    """Test the Trace JSON Encoder."""
    ha_json_enc = ExtendedJSONEncoder()
    state = core.State("test.test", "hello")

    # Test serializing a datetime
    now = dt_util.utcnow()
    assert ha_json_enc.default(now) == now.isoformat()

    # Test serializing a timedelta
    data = timedelta(
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

    # Test serializing a set()
    data = {"milk", "beer"}
    assert sorted(ha_json_enc.default(data)) == sorted(data)

    # Test serializong object which implements as_dict
    assert ha_json_enc.default(state) == state.as_dict()

    # Default method falls back to repr(o)
    o = object()
    assert ha_json_enc.default(o) == {"__type": str(type(o)), "repr": repr(o)}
