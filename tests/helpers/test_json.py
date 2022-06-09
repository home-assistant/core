"""Test Home Assistant remote methods and classes."""
import datetime

import pytest

from homeassistant import core
from homeassistant.helpers.json import ExtendedJSONEncoder, JSONEncoder
from homeassistant.util import dt as dt_util


@pytest.mark.parametrize("encoder", (JSONEncoder, ExtendedJSONEncoder))
def test_json_encoder(hass, encoder):
    """Test the JSON encoders."""
    ha_json_enc = encoder()
    state = core.State("test.test", "hello")

    # Test serializing a datetime
    now = dt_util.utcnow()
    assert ha_json_enc.default(now) == now.isoformat()

    # Test serializing a set()
    data = {"milk", "beer"}
    assert sorted(ha_json_enc.default(data)) == sorted(data)

    # Test serializing an object which implements as_dict
    assert ha_json_enc.default(state) == state.as_dict()


def test_json_encoder_raises(hass):
    """Test the JSON encoder raises on unsupported types."""
    ha_json_enc = JSONEncoder()

    # Default method raises TypeError if non HA object
    with pytest.raises(TypeError):
        ha_json_enc.default(1)


def test_extended_json_encoder(hass):
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
