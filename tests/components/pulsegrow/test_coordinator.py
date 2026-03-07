"""Tests for PulseGrow coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiopulsegrow import PulsegrowError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test coordinator handles API errors."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Simulate API error on next update
    mock_pulsegrow_client.get_all_devices.side_effect = PulsegrowError("API Error")

    # Get coordinator and trigger update
    coordinator = mock_config_entry.runtime_data
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_hub_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test coordinator successfully fetches hub data."""
    # Override get_hub_ids to return hub IDs (it's an AsyncMock)
    mock_hub = MagicMock()
    mock_hub.id = 100
    mock_hub.name = "Test Hub"
    mock_hub.mac_address = "AA:BB:CC:DD:EE:FF"

    mock_pulsegrow_client.get_hub_ids = AsyncMock(return_value=[100])
    mock_pulsegrow_client.get_hub_details = AsyncMock(return_value=mock_hub)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should have the hub
    coordinator = mock_config_entry.runtime_data
    assert len(coordinator.data.hubs) == 1
    assert "100" in coordinator.data.hubs


async def test_coordinator_hub_ids_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test coordinator handles hub IDs API errors gracefully."""
    mock_pulsegrow_client.get_hub_ids.side_effect = PulsegrowError("Cannot fetch hubs")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still work, just without hubs
    coordinator = mock_config_entry.runtime_data
    assert len(coordinator.data.hubs) == 0
    assert len(coordinator.data.devices) == 1


async def test_coordinator_with_sensors_from_device_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test coordinator processes sensors from DeviceData."""
    # Add sensors to the DeviceData
    mock_sensor = MagicMock()
    mock_sensor.id = 500
    mock_sensor.name = "Test Sensor"
    mock_sensor.sensor_type = "VWC"
    mock_sensor.hub_id = 100
    mock_sensor.most_recent_data_point = None

    mock_device_data = mock_pulsegrow_client.get_all_devices.return_value
    mock_device_data.sensors = [mock_sensor]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensor should be in coordinator data
    coordinator = mock_config_entry.runtime_data
    assert "500" in coordinator.data.sensors
