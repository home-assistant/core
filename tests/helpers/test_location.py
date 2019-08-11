"""Tests Home Assistant location helpers."""
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State
from homeassistant.helpers import location


def test_has_location_with_invalid_states():
    """Set up the tests."""
    for state in (None, 1, "hello", object):
        assert not location.has_location(state)


def test_has_location_with_states_with_invalid_locations():
    """Set up the tests."""
    state = State(
        "hello.world", "invalid", {ATTR_LATITUDE: "no number", ATTR_LONGITUDE: 123.12}
    )
    assert not location.has_location(state)


def test_has_location_with_states_with_valid_location():
    """Set up the tests."""
    state = State(
        "hello.world", "invalid", {ATTR_LATITUDE: 123.12, ATTR_LONGITUDE: 123.12}
    )
    assert location.has_location(state)


def test_closest_with_no_states_with_location():
    """Set up the tests."""
    state = State("light.test", "on")
    state2 = State(
        "light.test", "on", {ATTR_LATITUDE: "invalid", ATTR_LONGITUDE: 123.45}
    )
    state3 = State("light.test", "on", {ATTR_LONGITUDE: 123.45})

    assert location.closest(123.45, 123.45, [state, state2, state3]) is None


def test_closest_returns_closest():
    """Test ."""
    state = State("light.test", "on", {ATTR_LATITUDE: 124.45, ATTR_LONGITUDE: 124.45})
    state2 = State("light.test", "on", {ATTR_LATITUDE: 125.45, ATTR_LONGITUDE: 125.45})

    assert state == location.closest(123.45, 123.45, [state, state2])
