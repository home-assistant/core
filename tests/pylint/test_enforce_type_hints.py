"""Tests for pylint hass_enforce_type_hints plugin."""
# pylint:disable=protected-access

from importlib.machinery import SourceFileLoader
import re

import pytest

loader = SourceFileLoader(
    "hass_enforce_type_hints", "pylint/plugins/hass_enforce_type_hints.py"
)
hass_enforce_type_hints = loader.load_module(None)
_TYPE_HINT_MATCHERS: dict[str, re.Pattern] = hass_enforce_type_hints._TYPE_HINT_MATCHERS


@pytest.mark.parametrize(
    ("string", "expected_x", "expected_y", "expected_z"),
    [
        ("Callable[..., None]", "Callable", "...", "None"),
        ("Callable[..., Awaitable[None]]", "Callable", "...", "Awaitable[None]"),
    ],
)
def test_regex_x_of_y_comma_z(string, expected_x, expected_y, expected_z):
    """Test x_of_y_comma_z regexes."""
    assert (match := _TYPE_HINT_MATCHERS["x_of_y_comma_z"].match(string))
    assert match.group(0) == string
    assert match.group(1) == expected_x
    assert match.group(2) == expected_y
    assert match.group(3) == expected_z


@pytest.mark.parametrize(
    ("string", "expected_a", "expected_b"),
    [("DiscoveryInfoType | None", "DiscoveryInfoType", "None")],
)
def test_regex_a_or_b(string, expected_a, expected_b):
    """Test a_or_b regexes."""
    assert (match := _TYPE_HINT_MATCHERS["a_or_b"].match(string))
    assert match.group(0) == string
    assert match.group(1) == expected_a
    assert match.group(2) == expected_b
