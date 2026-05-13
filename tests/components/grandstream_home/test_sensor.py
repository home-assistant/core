# mypy: ignore-errors
"""Test Grandstream sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.grandstream_home import GrandstreamRuntimeData
from homeassistant.components.grandstream_home.sensor import (
    DEVICE_SENSORS,
    GrandstreamDeviceSensor,
    GrandstreamSensorEntityDescription,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


async def test_sensor_unavailable_mapping(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_device_info: MagicMock
) -> None:
    """Test sensor maps unavailable to no_available_account."""
    description = DEVICE_SENSORS[0]
    mock_coordinator.data = "unavailable"

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, mock_device_info, "test_unique_id", description
    )

    assert sensor.native_value == "no_available_account"


async def test_sensor_unknown_returns_none(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_device_info: MagicMock
) -> None:
    """Test sensor returns None for unknown state."""
    description = DEVICE_SENSORS[0]
    mock_coordinator.data = "unknown"

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, mock_device_info, "test_unique_id", description
    )

    assert sensor.native_value is None


async def test_sensor_strips_whitespace(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_device_info: MagicMock
) -> None:
    """Test sensor strips whitespace from value."""
    description = DEVICE_SENSORS[0]
    mock_coordinator.data = "idle "

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, mock_device_info, "test_unique_id", description
    )

    assert sensor.native_value == "idle"


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates sensors."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = "idle"

    mock_device_info = MagicMock()

    entry = MockConfigEntry(
        domain="grandstream_home",
        data={},
        unique_id="test_id",
    )
    entry.runtime_data = GrandstreamRuntimeData(
        api=MagicMock(),
        coordinator=mock_coordinator,
        device_info=mock_device_info,
        device_model="gds",
        product_model=None,
        unique_id="test_unique_id",
    )

    entities = []

    def mock_add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, mock_add_entities)

    assert len(entities) == 1
    assert entities[0].unique_id == "test_unique_id_phone_status"


async def test_sensor_without_value_fn(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_device_info: MagicMock
) -> None:
    """Test sensor without value_fn returns raw value."""

    # Create a description without value_fn
    description = GrandstreamSensorEntityDescription(
        key="test_sensor",
        translation_key="test",
    )
    mock_coordinator.data = "raw_value"

    sensor = GrandstreamDeviceSensor(
        mock_coordinator, mock_device_info, "test_unique_id", description
    )

    assert sensor.native_value == "raw_value"
