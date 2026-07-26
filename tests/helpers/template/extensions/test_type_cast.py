"""Test type casting functions for Home Assistant templates."""

import math

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError

from tests.helpers.template.helpers import render


def test_float_function(hass: HomeAssistant) -> None:
    """Test float function."""
    hass.states.async_set("sensor.temperature", "12")

    assert render(hass, "{{ float(states.sensor.temperature.state) }}") == 12.0

    assert render(hass, "{{ float(states.sensor.temperature.state) > 11 }}") is True

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ float('forgiving') }}")

    # Test handling of default return value
    assert render(hass, "{{ float('bad', 1) }}") == 1
    assert render(hass, "{{ float('bad', default=1) }}") == 1


def test_float_filter(hass: HomeAssistant) -> None:
    """Test float filter."""
    hass.states.async_set("sensor.temperature", "12")

    assert render(hass, "{{ states.sensor.temperature.state | float }}") == 12.0
    assert render(hass, "{{ states.sensor.temperature.state | float > 11 }}") is True

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'bad' | float }}")

    # Test handling of default return value
    assert render(hass, "{{ 'bad' | float(1) }}") == 1
    assert render(hass, "{{ 'bad' | float(default=1) }}") == 1


def test_int_filter(hass: HomeAssistant) -> None:
    """Test int filter."""
    hass.states.async_set("sensor.temperature", "12.2")
    assert render(hass, "{{ states.sensor.temperature.state | int }}") == 12
    assert render(hass, "{{ states.sensor.temperature.state | int > 11 }}") is True

    hass.states.async_set("sensor.temperature", "0x10")
    assert render(hass, "{{ states.sensor.temperature.state | int(base=16) }}") == 16

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'bad' | int }}")

    # Test handling of default return value
    assert render(hass, "{{ 'bad' | int(1) }}") == 1
    assert render(hass, "{{ 'bad' | int(default=1) }}") == 1


def test_int_function(hass: HomeAssistant) -> None:
    """Test int filter."""
    hass.states.async_set("sensor.temperature", "12.2")
    assert render(hass, "{{ int(states.sensor.temperature.state) }}") == 12
    assert render(hass, "{{ int(states.sensor.temperature.state) > 11 }}") is True

    hass.states.async_set("sensor.temperature", "0x10")
    assert render(hass, "{{ int(states.sensor.temperature.state, base=16) }}") == 16

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ int('bad') }}")

    # Test handling of default return value
    assert render(hass, "{{ int('bad', 1) }}") == 1
    assert render(hass, "{{ int('bad', default=1) }}") == 1


def test_bool_function(hass: HomeAssistant) -> None:
    """Test bool function."""
    assert render(hass, "{{ bool(true) }}") is True
    assert render(hass, "{{ bool(false) }}") is False
    assert render(hass, "{{ bool('on') }}") is True
    assert render(hass, "{{ bool('off') }}") is False
    with pytest.raises(TemplateError):
        render(hass, "{{ bool('unknown') }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ bool(none) }}")
    assert render(hass, "{{ bool('unavailable', none) }}") is None
    assert render(hass, "{{ bool('unavailable', default=none) }}") is None


def test_bool_filter(hass: HomeAssistant) -> None:
    """Test bool filter."""
    assert render(hass, "{{ true | bool }}") is True
    assert render(hass, "{{ false | bool }}") is False
    assert render(hass, "{{ 'on' | bool }}") is True
    assert render(hass, "{{ 'off' | bool }}") is False
    with pytest.raises(TemplateError):
        render(hass, "{{ 'unknown' | bool }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ none | bool }}")
    assert render(hass, "{{ 'unavailable' | bool(none) }}") is None
    assert render(hass, "{{ 'unavailable' | bool(default=none) }}") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True),
        (0.0, True),
        ("0", True),
        ("0.0", True),
        (True, True),
        (False, True),
        ("True", False),
        ("False", False),
        (None, False),
        ("None", False),
        ("horse", False),
        (math.pi, True),
        (math.nan, False),
        (math.inf, False),
        ("nan", False),
        ("inf", False),
    ],
)
def test_isnumber(hass: HomeAssistant, value: object, expected: bool) -> None:
    """Test is_number."""
    assert render(hass, "{{ is_number(value) }}", {"value": value}) == expected
    assert render(hass, "{{ value | is_number }}", {"value": value}) == expected
    assert render(hass, "{{ value is is_number }}", {"value": value}) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello", True),
        (b"hello", True),
        (bytearray(b"hello"), True),
        (42, False),
        ([1, 2], False),
        (None, False),
    ],
)
def test_string_like(hass: HomeAssistant, value: object, expected: bool) -> None:
    """Test string_like."""
    assert render(hass, "{{ value is string_like }}", {"value": value}) == expected
