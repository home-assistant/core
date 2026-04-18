"""Tests for the Home Assistant Labs integration."""

from typing import Any

from pytest_unordered import unordered


def assert_stored_labs_data(
    hass_storage: dict[str, Any],
    expected_data: list[dict[str, str]],
) -> None:
    """Assert that the storage has the expected enabled preview features."""
    assert hass_storage["core.labs"] == {
        "version": 1,
        "minor_version": 1,
        "key": "core.labs",
        "data": {"preview_feature_status": unordered(expected_data)},
    }
