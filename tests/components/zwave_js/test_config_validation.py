"""Test the Z-Wave JS config validation helpers."""
import pytest
import voluptuous as vol

from homeassistant.components.zwave_js.config_validation import boolean


def test_boolean_validation():
    """Test boolean config validator."""
    # test bool
    assert boolean(True)
    assert not boolean(False)
    # test strings
    assert boolean("TRUE")
    assert not boolean("FALSE")
    assert boolean("ON")
    assert not boolean("NO")
    # ensure 1's and 0's don't get converted to bool
    with pytest.raises(vol.Invalid):
        boolean("1")
    with pytest.raises(vol.Invalid):
        boolean("0")
    with pytest.raises(vol.Invalid):
        boolean(1)
    with pytest.raises(vol.Invalid):
        boolean(0)
