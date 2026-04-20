"""Tests for the Hive coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.hive.coordinator import HiveDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _make_device(hive_id: str = "hive-id-1", platform: str = "climate") -> dict[str, Any]:
    return {
        "hiveID": hive_id,
        "hiveType": platform,
        "device_id": f"dev-{hive_id}",
    }


@pytest.fixture
def mock_hive() -> MagicMock:
    """Return a mock Hive instance whose session has a known deviceList."""
    hive = MagicMock()
    climate_dev = _make_device("clim-1", "climate")
    light_dev = _make_device("light-1", "light")

    hive.session.deviceList = {
        "climate": [climate_dev],
        "binary_sensor": [],
        "sensor": [],
        "light": [light_dev],
        "switch": [],
        "water_heater": [],
    }
    hive.session.updateData = AsyncMock()
    hive.heating.getClimate = AsyncMock(return_value={**climate_dev, "status": {}})
    hive.light.getLight = AsyncMock(return_value={**light_dev, "status": {}})
    hive.sensor.getSensor = AsyncMock(return_value={})
    hive.switch.getSwitch = AsyncMock(return_value={})
    hive.hotwater.getWaterHeater = AsyncMock(return_value={})
    return hive


async def test_coordinator_returns_device_data_keyed_by_hive_id(
    hass: HomeAssistant,
    mock_hive: MagicMock,
) -> None:
    """Coordinator._async_update_data returns a dict keyed by hiveID."""
    entry = MockConfigEntry(domain="hive")
    coordinator = HiveDataUpdateCoordinator(hass, entry, mock_hive)

    data = await coordinator._async_update_data()

    assert ("clim-1", "climate") in data
    assert ("light-1", "light") in data
    assert data[("clim-1", "climate")]["hiveID"] == "clim-1"
    assert data[("light-1", "light")]["hiveID"] == "light-1"


async def test_coordinator_calls_update_data_for_each_device(
    hass: HomeAssistant,
    mock_hive: MagicMock,
) -> None:
    """UpdateData is called once per device."""
    entry = MockConfigEntry(domain="hive")
    coordinator = HiveDataUpdateCoordinator(hass, entry, mock_hive)
    await coordinator._async_update_data()

    assert mock_hive.session.updateData.call_count == 2  # climate + light
    mock_hive.heating.getClimate.assert_called_once()
    mock_hive.light.getLight.assert_called_once()


async def test_coordinator_skips_empty_platform_lists(
    hass: HomeAssistant,
    mock_hive: MagicMock,
) -> None:
    """Getters for empty platform lists are never called."""
    entry = MockConfigEntry(domain="hive")
    coordinator = HiveDataUpdateCoordinator(hass, entry, mock_hive)
    await coordinator._async_update_data()

    mock_hive.sensor.getSensor.assert_not_called()
    mock_hive.switch.getSwitch.assert_not_called()
    mock_hive.hotwater.getWaterHeater.assert_not_called()


def test_coordinator_update_interval_is_15_seconds(hass: HomeAssistant) -> None:
    """Coordinator polls every 15 seconds."""
    entry = MockConfigEntry(domain="hive")
    coordinator = HiveDataUpdateCoordinator(hass, entry, MagicMock())
    assert coordinator.update_interval == timedelta(seconds=15)


def test_coordinator_stores_hive_object(hass: HomeAssistant) -> None:
    """Coordinator exposes the Hive instance for entity access."""
    hive = MagicMock()
    entry = MockConfigEntry(domain="hive")
    coordinator = HiveDataUpdateCoordinator(hass, entry, hive)
    assert coordinator.hive is hive
