"""Tests for the ecobee.util module."""
import pytest
import voluptuous as vol

from homeassistant.components.ecobee.util import ecobee_date, ecobee_time, safe_list_get


def test_ecobee_date_with_valid_input():
    """Test that the date function returns the expected result."""
    test_input = "2019-09-27"

    assert ecobee_date(test_input) == test_input


def test_ecobee_date_with_invalid_input():
    """Test that the date function raises the expected exception."""
    test_input = "20190927"

    with pytest.raises(vol.Invalid):
        ecobee_date(test_input)


def test_ecobee_time_with_valid_input():
    """Test that the time function returns the expected result."""
    test_input = "20:55:15"

    assert ecobee_time(test_input) == test_input


def test_ecobee_time_with_invalid_input():
    """Test that the time function raises the expected exception."""
    test_input = "20:55"

    with pytest.raises(vol.Invalid):
        ecobee_time(test_input)


def test_safe_list_get_valid():
    """Test that the safe list get returns the expected result."""
    test_list = {"a": "a", "b": "b", "c": "c", "d": "d"}
    test_get_val = "c"
    test_default = "x"

    assert safe_list_get(test_list, test_get_val, test_default) == test_get_val


def test_safe_list_get_not_in_list_valid():
    """Test that the safe list get returns the default result."""
    test_list = {"a": "a", "b": "b", "c": "c", "d": "d"}
    test_get_val = "e"
    test_default = "x"

    assert safe_list_get(test_list, test_get_val, test_default) == test_default
