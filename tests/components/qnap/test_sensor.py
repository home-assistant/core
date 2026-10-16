"""Test the QNAP sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.qnap.sensor import _VOLUME_MON_COND, QNAPVolumeSensor

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
