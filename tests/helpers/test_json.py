"""Test Home Assistant remote methods and classes."""
from datetime import datetime, timedelta, timezone

import pytest

from homeassistant import core
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util import dt as dt_util


def test_json_encoder(hass):
    """Test the JSON Encoder."""
    ha_json_enc = JSONEncoder()
    state = core.State("test.test", "hello")

    # Test serializing a datetime
    data = datetime(2011, 11, 4, 0, 5, 23, 283000, tzinfo=timezone.utc)
    assert ha_json_enc.default(data) == data.isoformat()

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
    assert ha_json_enc.default(data) == str(data)

    # Test serializing a set()
    data = {"milk", "beer"}
    assert sorted(ha_json_enc.default(data)) == sorted(list(data))

    # Test serializong object which implements as_dict
    assert ha_json_enc.default(state) == state.as_dict()

    # Default method raises TypeError if non HA object
    with pytest.raises(TypeError):
        ha_json_enc.default(1)

    now = dt_util.utcnow()
    assert ha_json_enc.default(now) == now.isoformat()
