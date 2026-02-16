"""Tests for the EOL Tracker sensor integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from homeassistant.components.eol_tracker.sensor import BooleanEolSensor, EolSensor
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class DummyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Minimal stub for DataUpdateCoordinator."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize dummy coordinator with provided data."""
        self.data = data
        self.update_interval = timedelta(minutes=5)


@pytest.fixture
def full_data() -> dict[str, Any]:
    """Provide full example data for tests."""
    return {
        "release": {
            "label": "Ubuntu 20.04",
            "releaseDate": "2020-04-23",
            "isLts": True,
            "isEol": False,
            "isDiscontinued": False,
            "isMaintained": True,
            "latest": "20.04.6",
            "eolFrom": "2025-04-01",
            "custom": {"supported_os": "Linux"},
        },
        "product": {
            "label": "Ubuntu",
            "links": {
                "html": "https://endoflife.date/ubuntu",
                "icon": "https://endoflife.date/icons/ubuntu.png",
                "releasePolicy": "https://endoflife.date/ubuntu/policy",
            },
        },
    }


def test_eol_sensor_with_full_data(full_data: dict[str, Any]) -> None:
    """Test EolSensor behavior with full data."""
    coordinator = DummyCoordinator(full_data)
    sensor = EolSensor(coordinator, "Ubuntu", "20.04", "entry123")

    assert sensor.device_class == "timestamp"
    assert sensor.entity_picture == "https://endoflife.date/icons/ubuntu.png"

    attributes = sensor.extra_state_attributes
    assert attributes["Release Date:"] == "2020-04-23"
    assert attributes["Latest:"] == "20.04.6"
    assert attributes["End of Life from:"] == "2025-04-01"
    assert attributes["endoflife.date link:"] == "https://endoflife.date/ubuntu"
    assert attributes["Release Policy:"] == "https://endoflife.date/ubuntu/policy"
    assert attributes["Supported OS Versions:"] == "Linux"

    assert sensor._attr_unique_id is not None
    assert "entry123_20.04" in sensor._attr_unique_id

    assert sensor._attr_device_info is not None
    assert sensor._attr_device_info["model"] == "Ubuntu 20.04"


@pytest.mark.parametrize(("value", "expected"), [(True, "Yes"), (False, "No")])
def test_boolean_eol_sensor_states(
    full_data: dict[str, Any], value: bool, expected: str
) -> None:
    """Test BooleanEolSensor states based on input value."""
    coordinator = DummyCoordinator(full_data)
    sensor = BooleanEolSensor(coordinator, "Ubuntu", "20.04", "LTS", value, "entry123")

    assert sensor.native_value == expected
    assert sensor.device_class is None
    assert sensor.extra_state_attributes == {"name": "LTS"}

    assert sensor._attr_icon is not None
    assert ("check-circle" in sensor._attr_icon) == value
    assert ("close-circle" in sensor._attr_icon) == (not value)


def test_missing_release_and_product() -> None:
    """Test sensor behavior when release and product info are missing."""
    coordinator = DummyCoordinator({"release": {}, "product": {}})
    sensor = EolSensor(coordinator, "Test", "1.0", "entry")

    attributes = sensor.extra_state_attributes
    assert attributes["Release Date:"] == "Unknown"
    assert attributes["Supported OS Versions:"] is None
    assert attributes["endoflife.date link:"] is None


def test_custom_field_non_dict() -> None:
    """Test sensor handles a custom field that is not a dictionary."""
    coordinator = DummyCoordinator(
        {
            "release": {"releaseDate": "2021-01-01", "custom": "not_dict"},
            "product": {"links": {}},
        }
    )
    sensor = EolSensor(coordinator, "Test", "1.0", "entryY")

    attributes = sensor.extra_state_attributes
    assert attributes["Supported OS Versions:"] is None


def test_device_info_consistency(full_data: dict[str, Any]) -> None:
    """Test device info fields are consistent and unique IDs are lowercase."""
    coordinator = DummyCoordinator(full_data)
    sensor = EolSensor(coordinator, "Ubuntu", "20.04", "entryABC")
    boolean_sensor = BooleanEolSensor(
        coordinator, "Ubuntu", "20.04", "EOL", True, "entryABC"
    )

    assert sensor._attr_device_info is not None
    assert sensor._attr_device_info["manufacturer"] == "endoflife.date"
    assert boolean_sensor._attr_device_info is not None
    assert boolean_sensor._attr_device_info["name"] == "Ubuntu 20.04 EOL"
    assert sensor._attr_unique_id is not None
    assert "_" in sensor._attr_unique_id
    assert sensor._attr_unique_id == sensor._attr_unique_id.lower()
