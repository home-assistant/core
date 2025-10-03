import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.components.cover import STATE_CLOSED, STATE_OPEN
from homeassistant.components.ryse.cover import SmartShadeCover

@pytest.mark.asyncio
@pytest.fixture
def mock_ble_device():
    """Mock the RyseBLEDevice class."""
    with patch("components.ryse.cover.RyseBLEDevice") as mock_device:
        instance = mock_device.return_value
        instance.pair = AsyncMock(return_value=True)
        instance.read_data = AsyncMock(return_value=b"\xF5\x03\x01\x01\x64")
        instance.write_data = AsyncMock()
        yield instance

@pytest.mark.asyncio
async def test_cover_open(mock_ble_device, hass):
    """Test opening the cover."""
    cover = SmartShadeCover(mock_ble_device)

    await cover.async_open_cover()
    mock_ble_device.write_data.assert_called_once()
    assert cover.state == STATE_OPEN

@pytest.mark.asyncio
async def test_cover_close(mock_ble_device, hass):
    """Test closing the cover."""
    cover = SmartShadeCover(mock_ble_device)

    await cover.async_close_cover()
    mock_ble_device.write_data.assert_called_once()
    assert cover.state == STATE_CLOSED
