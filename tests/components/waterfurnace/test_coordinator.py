"""Tests for WaterFurnace coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from waterfurnace.waterfurnace import WFException, WFReading

from homeassistant.components.waterfurnace.const import UPDATE_INTERVAL
from homeassistant.components.waterfurnace.coordinator import WaterFurnaceCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import async_load_json_object_fixture


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, mock_waterfurnace_client: MagicMock
) -> WaterFurnaceCoordinator:
    """Create a WaterFurnace coordinator."""
    return WaterFurnaceCoordinator(hass, mock_waterfurnace_client)


class TestWaterFurnaceCoordinator:
    """Test WaterFurnace coordinator."""

    async def test_coordinator_initialization(
        self, hass: HomeAssistant, mock_waterfurnace_client: MagicMock
    ) -> None:
        """Test coordinator initialization."""
        coordinator = WaterFurnaceCoordinator(hass, mock_waterfurnace_client)

        assert coordinator.client is mock_waterfurnace_client
        assert coordinator.unit == "device_123"
        assert coordinator.update_interval == UPDATE_INTERVAL
        assert coordinator.name == "WaterFurnace"

    async def test_coordinator_initialization_with_config_entry(
        self, hass: HomeAssistant, mock_waterfurnace_client: MagicMock
    ) -> None:
        """Test coordinator initialization with config entry."""
        mock_config_entry = MagicMock()
        coordinator = WaterFurnaceCoordinator(
            hass, mock_waterfurnace_client, config_entry=mock_config_entry
        )

        assert coordinator.config_entry is mock_config_entry
        assert coordinator.client is mock_waterfurnace_client

    async def test_coordinator_async_update_data_success(
        self, hass: HomeAssistant, coordinator: WaterFurnaceCoordinator
    ) -> None:
        """Test successful data update."""
        data = await coordinator._async_update_data()

        # Verify the data returned is correct
        assert data is not None
        assert isinstance(data, WFReading)
        assert data.totalunitpower == 1500
        assert data.compressorpower == 800

    async def test_coordinator_async_update_data_with_retry(
        self, hass: HomeAssistant, mock_waterfurnace_client: MagicMock
    ) -> None:
        """Test data update uses read_with_retry."""
        coordinator = WaterFurnaceCoordinator(hass, mock_waterfurnace_client)

        await coordinator._async_update_data()

        # Verify read_with_retry was called (not just read)
        mock_waterfurnace_client.read_with_retry.assert_called_once()

    async def test_coordinator_async_update_data_exception(
        self, hass: HomeAssistant
    ) -> None:
        """Test data update handles WFException."""
        client = MagicMock()
        client.gwid = "device_123"
        client.read_with_retry = MagicMock(side_effect=WFException("Connection failed"))

        coordinator = WaterFurnaceCoordinator(hass, client)

        with pytest.raises(UpdateFailed, match="Connection failed"):
            await coordinator._async_update_data()

    async def test_coordinator_async_update_data_timeout(
        self, hass: HomeAssistant
    ) -> None:
        """Test data update handles timeout."""
        client = MagicMock()
        client.gwid = "device_123"
        client.read_with_retry = MagicMock(side_effect=TimeoutError("Request timeout"))

        coordinator = WaterFurnaceCoordinator(hass, client)

        with pytest.raises(asyncio.TimeoutError):
            await coordinator._async_update_data()

    async def test_coordinator_reads_sensor_values(
        self, hass: HomeAssistant, coordinator: WaterFurnaceCoordinator
    ) -> None:
        """Test coordinator data contains expected sensor values."""
        data = await coordinator._async_update_data()

        assert data.leavingairtemp == 110.5
        assert data.tstatroomtemp == 70.2
        assert data.enteringwatertemp == 42.8
        assert data.tstatactivesetpoint == 72
        assert data.tstatrelativehumidity == 43
        assert data.tstathumidsetpoint == 45
        assert data.airflowcurrentspeed == 850
        assert data.actualcompressorspeed == 1200
        assert data.fanpower == 150
        assert data.auxpower == 0
        assert data.looppumppower == 50

    async def test_coordinator_multiple_updates(
        self, hass: HomeAssistant, mock_waterfurnace_client: MagicMock
    ) -> None:
        """Test coordinator can perform multiple updates."""
        coordinator = WaterFurnaceCoordinator(hass, mock_waterfurnace_client)

        # First update
        first_data = await coordinator._async_update_data()

        # Modify mock return value for second update
        reading_data = await async_load_json_object_fixture(
            hass, "device_data.json", "waterfurnace"
        )
        reading_data["compressorpower"] = 1000
        mock_waterfurnace_client.read_with_retry.return_value = WFReading(reading_data)

        # Second update
        second_data = await coordinator._async_update_data()

        assert first_data.compressorpower == 800
        assert second_data.compressorpower == 1000
