"""Tests for the EOL Tracker sensor integration."""

from datetime import timedelta
from typing import Any

import pytest

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .sensor import BooleanEolSensor, EolSensor


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
    coord = DummyCoordinator(full_data)
    sensor = EolSensor(coord, "Ubuntu", "20.04", "entry123")

    assert sensor.device_class == "timestamp"
    assert sensor.entity_picture == "https://endoflife.date/icons/ubuntu.png"

    attrs = sensor.extra_state_attributes
    assert attrs["Release Date:"] == "2020-04-23"
    assert attrs["Latest:"] == "20.04.6"
    assert attrs["End of Life from:"] == "2025-04-01"
    assert attrs["endoflife.date link:"] == "https://endoflife.date/ubuntu"
    assert attrs["Release Policy:"] == "https://endoflife.date/ubuntu/policy"
    assert attrs["Supported OS Versions:"] == "Linux"

    assert sensor._attr_unique_id is not None  # noqa: SLF001
    assert "entry123_20.04" in sensor._attr_unique_id  # noqa: SLF001

    assert sensor._attr_device_info is not None  # noqa: SLF001
    assert sensor._attr_device_info["model"] == "Ubuntu 20.04"  # noqa: SLF001


@pytest.mark.parametrize(("value", "expected"), [(True, "Yes"), (False, "No")])
def test_boolean_eol_sensor_states(
    full_data: dict[str, Any], value: bool, expected: str
) -> None:
    """Test BooleanEolSensor states based on input value."""
    coord = DummyCoordinator(full_data)
    bsensor = BooleanEolSensor(coord, "Ubuntu", "20.04", "LTS", value, "entry123")

    assert bsensor.native_value == expected
    assert bsensor.device_class is None
    assert bsensor.extra_state_attributes == {"name": "LTS"}

    icon = bsensor._attr_icon  # noqa: SLF001
    assert icon is not None
    assert ("check-circle" in icon) == value
    assert ("close-circle" in icon) == (not value)


def test_missing_release_and_product() -> None:
    """Test sensor behavior when release and product info are missing."""
    coord = DummyCoordinator({"release": {}, "product": {}})
    sensor = EolSensor(coord, "Test", "1.0", "entry")

    attrs = sensor.extra_state_attributes
    assert attrs["Release Date:"] == "Unknown"
    assert attrs["Supported OS Versions:"] is None
    assert attrs["endoflife.date link:"] is None


def test_custom_field_non_dict() -> None:
    """Test sensor handles 'custom' field that is not a dictionary."""
    data = {
        "release": {"releaseDate": "2021-01-01", "custom": "notDict"},
        "product": {"links": {}},
    }
    coord = DummyCoordinator(data)
    sensor = EolSensor(coord, "Test", "1.0", "entryY")

    attrs = sensor.extra_state_attributes
    assert attrs["Supported OS Versions:"] is None


def test_device_info_consistency(full_data: dict[str, Any]) -> None:
    """Test device info fields are consistent and unique IDs are lowercase."""
    coord = DummyCoordinator(full_data)
    sensor = EolSensor(coord, "Ubuntu", "20.04", "entryABC")
    bsensor = BooleanEolSensor(coord, "Ubuntu", "20.04", "EOL", True, "entryABC")

    assert sensor._attr_device_info is not None  # noqa: SLF001
    assert sensor._attr_device_info["manufacturer"] == "endoflife.date"  # noqa: SLF001
    assert bsensor._attr_device_info is not None  # noqa: SLF001
    assert bsensor._attr_device_info["name"] == "Ubuntu 20.04 EOL"  # noqa: SLF001
    assert sensor._attr_unique_id is not None  # noqa: SLF001
    assert "_" in sensor._attr_unique_id  # noqa: SLF001
    assert sensor._attr_unique_id == sensor._attr_unique_id.lower()  # noqa: SLF001
