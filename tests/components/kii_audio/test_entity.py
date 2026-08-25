"""Tests for Kii Audio entity helpers."""

from copy import deepcopy

from homeassistant.components.kii_audio.entity import get_path, zone_device_info

from .conftest import FakeCoordinator, make_zone


def test_zone_device_info_handles_missing_optional_zone_data() -> None:
    """Test device info falls back when optional zone data is missing."""
    zone = {"zoneId": "zone-id"}
    coordinator = FakeCoordinator(make_zone())

    device_info = zone_device_info(coordinator, "zone-id", zone)

    assert device_info["model"] is None
    assert device_info["name"] == "zone-id"


def test_zone_device_info_ignores_duplicate_models() -> None:
    """Test model summary ignores duplicate models."""
    zone = make_zone()
    zone["devices"] = [
        {"modelName": "Kii Seven"},
        {"modelName": "Kii Seven"},
    ]
    coordinator = FakeCoordinator(deepcopy(zone))

    device_info = zone_device_info(coordinator, "zone-id", zone)

    assert device_info["model"] == "Kii Seven"


def test_get_path_returns_nested_values() -> None:
    """Test dotted-path lookup returns nested values."""
    assert get_path({"audio": {"volume": -40.0}}, "audio.volume") == -40.0


def test_get_path_returns_none_for_invalid_path() -> None:
    """Test dotted-path lookup returns None for invalid intermediate data."""
    assert get_path({"audio": "invalid"}, "audio.volume") is None


def test_zone_device_info_handles_empty_model_list() -> None:
    """Test device info has no model when no valid models are present."""
    zone = make_zone()
    zone["devices"] = [{"modelName": ""}]
    coordinator = FakeCoordinator(make_zone())

    device_info = zone_device_info(coordinator, "zone-id", zone)

    assert device_info["model"] is None
