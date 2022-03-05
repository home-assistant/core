"""Test the Z-Wave JS config validation helpers."""
import pytest
import voluptuous as vol

from homeassistant.components.zwave_js.config_validation import boolean


def test_boolean_validation():
    """Test boolean config validator."""
    assert boolean(True)
    assert not boolean(False)
    assert boolean("TRUE")
    assert not boolean("FALSE")
    assert boolean("ON")
    assert not boolean("NO")
    with pytest.raises(vol.Invalid):
        boolean("1")
    with pytest.raises(vol.Invalid):
        boolean("0")
