"""Test module for IoTMeter DataUpdateCoordinator in Home Assistant."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.components.iotmeter.coordinator import IotMeterDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
async def mock_hass(tmpdir):
    """Fixture for Home Assistant instance."""
    hass = HomeAssistant(tmpdir)
    await hass.async_start()
    await hass.async_block_till_done()
    yield hass
    await hass.async_stop()


@pytest.fixture
def mock_coordinator(mock_hass):
    """Fixture for IotMeterDataUpdateCoordinator."""
    return IotMeterDataUpdateCoordinator(mock_hass, "192.168.1.1", 8000)


@pytest.mark.asyncio
async def test_update_ip_port(mock_coordinator):
    """Test updating IP address and port."""
    mock_coordinator.update_ip_port("192.168.1.2", 9000)
    assert mock_coordinator.ip_address == "192.168.1.2"
    assert mock_coordinator.port == 9000


@pytest.mark.asyncio
async def test_async_update_data(mock_coordinator):
    """Test fetching data from API."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"data": "value"})
        mock_get.return_value.__aenter__.return_value = mock_response

        data = await mock_coordinator._async_update_data()
        assert data == {"data": "value"}


@pytest.mark.asyncio
async def test_async_update_data_fail(mock_coordinator):
    """Test handling failure during data fetch."""
    with (
        patch("aiohttp.ClientSession.get", side_effect=aiohttp.ClientError),
        pytest.raises(UpdateFailed),
    ):
        await mock_coordinator._async_update_data()


@pytest.mark.asyncio
async def test_add_sensor_entities(mock_coordinator):
    """Test adding sensor entities."""
    mock_coordinator.async_add_sensor_entities = AsyncMock()
    with patch(
        "homeassistant.helpers.translation.async_get_translations", return_value={}
    ):
        await mock_coordinator.add_sensor_entities()
        assert len(mock_coordinator.entities) > 0
        mock_coordinator.async_add_sensor_entities.assert_called_once()


@pytest.mark.asyncio
async def test_add_number_entities(mock_coordinator):
    """Test adding number entities."""
    mock_coordinator.async_add_number_entities = AsyncMock()
    with patch(
        "homeassistant.helpers.translation.async_get_translations", return_value={}
    ):
        await mock_coordinator.add_number_entities("1.0")
        assert len(mock_coordinator.entities) > 0
        mock_coordinator.async_add_number_entities.assert_called_once()


@pytest.mark.asyncio
async def test_remove_entities(mock_coordinator):
    """Test removing entities."""
    entity = AsyncMock()
    mock_coordinator.entities = [entity]
    await mock_coordinator.remove_entities()
    assert len(mock_coordinator.entities) == 0
    entity.async_remove.assert_called_once()
