"""Tests for data navigation and value extraction."""
from __future__ import annotations

from typing import Any

import pytest

from .conftest import get_value


def test_get_value_top_level(mock_pool_data: dict[str, Any]) -> None:
    """Test getting a top-level key."""
    assert get_value(mock_pool_data, "present") is True


def test_get_value_nested(mock_pool_data: dict[str, Any]) -> None:
    """Test getting a nested value."""
    assert get_value(mock_pool_data, "main.temperature") == 25.5


def test_get_value_deep_nested(mock_pool_data: dict[str, Any]) -> None:
    """Test getting a deeply nested value."""
    assert get_value(mock_pool_data, "modules.ph.current") == "742"


def test_get_value_missing_returns_default(mock_pool_data: dict[str, Any]) -> None:
    """Test missing path returns default."""
    assert get_value(mock_pool_data, "nonexistent.path") is None
    assert get_value(mock_pool_data, "nonexistent.path", "fallback") == "fallback"


def test_get_value_module_presence(mock_pool_data: dict[str, Any]) -> None:
    """Test checking module presence flags."""
    assert get_value(mock_pool_data, "main.hasPH") == 1
    assert get_value(mock_pool_data, "main.hasRX") == 1
    assert get_value(mock_pool_data, "main.hasCD") == 0
    assert get_value(mock_pool_data, "main.hasCL") == 0
    assert get_value(mock_pool_data, "main.hasUV") == 0
    assert get_value(mock_pool_data, "main.hasHidro") == 1


def test_get_value_filtration_intervals(mock_pool_data: dict[str, Any]) -> None:
    """Test reading filtration interval values."""
    assert get_value(mock_pool_data, "filtration.interval1.from") == 28800
    assert get_value(mock_pool_data, "filtration.interval1.to") == 36000
    assert get_value(mock_pool_data, "filtration.interval2.from") == 46800


def test_get_value_relay_status(mock_pool_data: dict[str, Any]) -> None:
    """Test reading relay onoff/status values."""
    assert get_value(mock_pool_data, "relays.relay1.info.onoff") == 0
    assert get_value(mock_pool_data, "relays.relay1.info.status") == 0


def test_get_value_form_data(mock_pool_data: dict[str, Any]) -> None:
    """Test reading form (location) data."""
    assert get_value(mock_pool_data, "form.city") == "Waterloo"
    assert get_value(mock_pool_data, "form.country") == "BE"


def test_get_value_electrolysis_flag(mock_pool_data: dict[str, Any]) -> None:
    """Test reading the is_electrolysis boolean."""
    assert get_value(mock_pool_data, "hidro.is_electrolysis") is True
