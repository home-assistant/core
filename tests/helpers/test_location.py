"""Tests Home Assistant location helpers."""
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_LATITUDE, ATTR_LONGITUDE
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


async def test_coordinates_function_as_attributes(hass):
    """Test coordinates function."""
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    assert location.find_coordinates(hass, "test.object") == "32.87336,-117.22943"


async def test_coordinates_function_as_state(hass):
    """Test coordinates function."""
    hass.states.async_set("test.object", "32.87336,-117.22943")
    assert location.find_coordinates(hass, "test.object") == "32.87336,-117.22943"


async def test_coordinates_function_device_tracker_in_zone(hass):
    """Test coordinates function."""
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"latitude": 32.87336, "longitude": -117.22943},
    )
    hass.states.async_set("device_tracker.device", "home")
    assert (
        location.find_coordinates(hass, "device_tracker.device")
        == "32.87336,-117.22943"
    )


async def test_coordinates_function_zone_friendly_name(hass):
    """Test coordinates function."""
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"latitude": 32.87336, "longitude": -117.22943, ATTR_FRIENDLY_NAME: "my_home"},
    )
    hass.states.async_set(
        "test.object",
        "my_home",
    )
    assert location.find_coordinates(hass, "test.object") == "32.87336,-117.22943"
    assert location.find_coordinates(hass, "my_home") == "32.87336,-117.22943"


async def test_coordinates_function_device_tracker_from_input_select(hass):
    """Test coordinates function."""
    hass.states.async_set(
        "input_select.select",
        "device_tracker.device",
        {"options": "device_tracker.device"},
    )
    hass.states.async_set("device_tracker.device", "32.87336,-117.22943")
    assert (
        location.find_coordinates(hass, "input_select.select") == "32.87336,-117.22943"
    )


def test_coordinates_function_returns_none_on_recursion(hass):
    """Test coordinates function."""
    hass.states.async_set(
        "test.first",
        "test.second",
    )
    hass.states.async_set("test.second", "test.first")
    assert location.find_coordinates(hass, "test.first") is None


async def test_coordinates_function_returns_state_if_no_coords(hass):
    """Test test_coordinates function."""
    hass.states.async_set(
        "test.object",
        "abc",
    )
    assert location.find_coordinates(hass, "test.object") == "abc"


def test_coordinates_function_returns_input_if_no_coords(hass):
    """Test test_coordinates function."""
    assert location.find_coordinates(hass, "test.abc") == "test.abc"
    assert location.find_coordinates(hass, "abc") == "abc"
