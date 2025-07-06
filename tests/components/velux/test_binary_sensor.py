"""Tests for the Velux rain sensor binary_sensor platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyvlx.exception import PyVLXException

from homeassistant.components.velux.binary_sensor import VeluxRainSensor


@pytest.fixture
def mock_window():
    """Return a mock Velux window with a rain sensor."""
    node = MagicMock(spec=["name", "rain_sensor", "get_limitation", "serial_number"])
    node.name = "Test Window"
    node.rain_sensor = True
    node.serial_number = "1234567890"
    return node


@pytest.fixture
def mock_limitation_rain():
    """Return a mock limitation object indicating rain detected."""
    limitation = MagicMock()
    limitation.max_value = 100
    limitation.min_value = 93
    return limitation


@pytest.fixture
def mock_limitation_dry():
    """Return a mock limitation object indicating no rain."""
    limitation = MagicMock()
    limitation.max_value = 100
    limitation.min_value = 0
    return limitation


@pytest.mark.asyncio
async def test_rain_sensor_detected(mock_window, mock_limitation_rain) -> None:
    """Test VeluxRainSensor is_on is True when rain is detected."""
    mock_window.get_limitation = AsyncMock(return_value=mock_limitation_rain)
    sensor = VeluxRainSensor(mock_window, "test_entry_id")
    await sensor.async_update()
    assert sensor.is_on is True


@pytest.mark.asyncio
async def test_rain_sensor_not_detected(mock_window, mock_limitation_dry) -> None:
    """Test VeluxRainSensor is_on is False when rain is not detected."""
    mock_window.get_limitation = AsyncMock(return_value=mock_limitation_dry)
    sensor = VeluxRainSensor(mock_window, "test_entry_id")
    await sensor.async_update()
    assert sensor.is_on is False


@pytest.mark.asyncio
async def test_rain_sensor_update_error(mock_window) -> None:
    """Test VeluxRainSensor handles PyVLXException gracefully."""

    mock_window.get_limitation = AsyncMock(side_effect=PyVLXException("Test error"))
    sensor = VeluxRainSensor(mock_window, "test_entry_id")
    await sensor.async_update()
    # Should remain default (False)
    assert sensor.is_on is False


def test_unique_id_and_name(mock_window) -> None:
    """Test unique_id and name are set correctly."""
    sensor = VeluxRainSensor(mock_window, "test_entry_id")
    assert sensor._attr_unique_id.endswith("_rain_sensor")
    assert sensor._attr_name == "Test Window Rain Sensor"
