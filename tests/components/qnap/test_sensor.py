"""Test the QNAP sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.qnap.sensor import (
    _SYSTEM_MON_COND,
    _VOLUME_MON_COND,
    QNAPSystemSensor,
    QNAPVolumeSensor,
)

from .conftest import TEST_SERIAL


def _make_coordinator(volumes: dict) -> MagicMock:
    """Create a mock coordinator with the given volumes."""
    coordinator = MagicMock()
    coordinator.data = {
        "system_stats": {
            "system": {"name": "Test NAS", "model": "TS-1"},
            "firmware": {"version": "1.0"},
        },
        "volumes": volumes,
    }
    return coordinator


def _volume_sensor(coordinator: MagicMock) -> QNAPVolumeSensor:
    """Create a volume percentage sensor."""
    description = next(
        desc for desc in _VOLUME_MON_COND if desc.key == "volume_percentage_used"
    )
    return QNAPVolumeSensor(coordinator, description, TEST_SERIAL, "Volume 1")


@pytest.mark.parametrize(
    ("free_size", "total_size", "expected"),
    [
        (75, 100, 25.0),
        (0, 0, None),
    ],
)
def test_volume_percentage_used(
    free_size: int, total_size: int, expected: float | None
) -> None:
    """Test the volume percentage used sensor."""
    coordinator = _make_coordinator(
        {"Volume 1": {"free_size": free_size, "total_size": total_size}}
    )
    sensor = _volume_sensor(coordinator)
    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("temp_c", "expected"),
    [
        (42, 42),
        ("42", 42),
        (None, None),
    ],
)
def test_system_temperature(temp_c: int | str | None, expected: int | None) -> None:
    """Test the system temperature sensor handles a missing reading."""
    coordinator = _make_coordinator({})
    coordinator.data["system_stats"]["system"]["temp_c"] = temp_c
    description = next(desc for desc in _SYSTEM_MON_COND if desc.key == "system_temp")
    sensor = QNAPSystemSensor(coordinator, description, TEST_SERIAL)
    assert sensor.native_value == expected
