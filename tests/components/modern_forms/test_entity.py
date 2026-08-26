"""Tests for the Modern Forms entity helpers."""

import pytest

from homeassistant.components.modern_forms.entity import strip_device_name_prefix


@pytest.mark.parametrize(
    ("device_name", "name", "expected"),
    [
        pytest.param(
            "Master Bedroom",
            "Master Bedroom Uplight",
            "Uplight",
            id="exact_prefix",
        ),
        pytest.param(
            "master bedroom",
            "Master Bedroom Uplight",
            "Uplight",
            id="case_insensitive",
        ),
        pytest.param(
            "Master Bedroom",
            "Master Bedroom - Uplight",
            "Uplight",
            id="dash_separator",
        ),
        pytest.param(
            "Master Bedroom",
            "Uplight",
            "Uplight",
            id="no_prefix_present",
        ),
        pytest.param(
            "Master Bedroom",
            "Master Bedroom",
            "Master Bedroom",
            id="fixture_named_exactly_like_device",
        ),
        pytest.param(
            "",
            "Uplight",
            "Uplight",
            id="empty_device_name",
        ),
    ],
)
def test_strip_device_name_prefix(device_name: str, name: str, expected: str) -> None:
    """Test stripping a leading device-name prefix from a fixture name."""
    assert strip_device_name_prefix(device_name, name) == expected
