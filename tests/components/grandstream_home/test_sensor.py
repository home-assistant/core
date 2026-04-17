# mypy: ignore-errors
"""Test Grandstream sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.grandstream_home.sensor import (
    DEVICE_SENSORS,
    GrandstreamDeviceSensor,
    GrandstreamSensorEntityDescription,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = "idle"
    coordinator.last_update_success = True
    return coordinator


@pytest.fixture
def mock_device_info():
    """Create mock device info."""
    return MagicMock()


async def test_sensor_setup(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_device_info: MagicMock
) -> None:
    """Test sensor setup."""
    # Create sensor
    description = DEVICE_SENSORS[0]
    sensor = GrandstreamDeviceSensor(
        mock_coordinator, mock_device_info, "test_unique_id", description
    )

    # Check initial state
    assert sensor.native_value == "idle"
    assert sensor.unique_id == "test_unique_id_phone_status"


async def test_sensor_native_value(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_device_info: MagicMock
) -> None:
    """Test sensor native value from coordinator."""
    description = DEVICE_SENSORS[0]

    # Test different states
    for state in ("idle", "ringing", "in_call"):
        mock_coordinator.data = state
        sensor = GrandstreamDeviceSensor(
            mock_coordinator, mock_device_info, "test_unique_id", description
        )
        assert sensor.native_value == state


async def test_sensor_unique_id() -> None:
    """Test sensor unique ID."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = "idle"
    device_info = MagicMock()
    description = DEVICE_SENSORS[0]

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, device_info, "test_unique_id", description
    )

    assert sensor.unique_id == "test_unique_id_phone_status"


def test_sensor_entity_description() -> None:
    """Test sensor entity description."""
    description = GrandstreamSensorEntityDescription(
        key="test_sensor",
        translation_key="test_translation",
    )

    assert description.key == "test_sensor"
    assert description.translation_key == "test_translation"
    assert description.key_path is None
