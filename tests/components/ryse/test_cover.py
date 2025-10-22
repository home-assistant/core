"""Tests for the Ryse Cover integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ryse.cover import SmartShadeCover
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_ble_device():
    """Mock the RyseBLEDevice class."""
    with patch("components.ryse.cover.RyseBLEDevice") as mock_device:
        instance = mock_device.return_value
        instance.pair = AsyncMock(return_value=True)
        instance.read_data = AsyncMock(return_value=b"\xf5\x03\x01\x01\x64")
        instance.write_data = AsyncMock()
        yield instance


@pytest.mark.asyncio
async def test_cover_open(mock_ble_device, hass: HomeAssistant) -> None:
    """Test opening the cover."""
    cover = SmartShadeCover(mock_ble_device)

    await cover.async_open_cover()
    mock_ble_device.write_data.assert_called_once()
    assert cover.state == STATE_OPEN


@pytest.mark.asyncio
async def test_cover_close(mock_ble_device, hass: HomeAssistant) -> None:
    """Test closing the cover."""
    cover = SmartShadeCover(mock_ble_device)

    await cover.async_close_cover()
    mock_ble_device.write_data.assert_called_once()
    assert cover.state == STATE_CLOSED
