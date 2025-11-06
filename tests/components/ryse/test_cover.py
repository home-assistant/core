"""Test RYSE Cover entity behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.components.ryse.cover import RyseCoverEntity


@pytest.fixture
def mock_device():
    """Mock RyseBLEDevice."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.is_valid_position.return_value = True
    device.get_real_position.side_effect = lambda x: x
    device.is_closed.side_effect = lambda x: x == 0
    return device


@pytest.mark.asyncio
async def test_cover_properties(mock_device) -> None:
    """Test properties of RyseCoverEntity."""
    entity = RyseCoverEntity(mock_device)

    info = entity.device_info
    assert info["manufacturer"] == "RYSE"
    assert "AA:BB" in info["identifiers"].pop()[1]
    assert entity._attr_supported_features & CoverEntityFeature.OPEN


@pytest.mark.asyncio
async def test_update_position_valid(mock_device) -> None:
    """Test updating position calls HA state write."""
    entity = RyseCoverEntity(mock_device)
    entity.async_write_ha_state = AsyncMock()

    await entity._update_position(50)
    mock_device.is_valid_position.assert_called_with(50)
    entity.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_async_open_close_and_set_cover(mock_device) -> None:
    """Test open, close and set cover methods."""
    mock_device.send_open = AsyncMock()
    mock_device.send_close = AsyncMock()
    mock_device.send_set_position = AsyncMock()
    entity = RyseCoverEntity(mock_device)

    await entity.async_open_cover()
    await entity.async_close_cover()
    await entity.async_set_cover_position(**{ATTR_POSITION: 75})

    mock_device.send_open.assert_awaited()
    mock_device.send_close.assert_awaited()
    mock_device.send_set_position.assert_awaited()


@pytest.mark.asyncio
async def test_async_update_handles_exceptions(mock_device) -> None:
    """Test BLE communication errors handled gracefully."""
    entity = RyseCoverEntity(mock_device)
    mock_device.client = None
    mock_device.pair = AsyncMock(return_value=False)

    await entity.async_update()
    assert entity._attr_available is False


@pytest.mark.asyncio
async def test_current_cover_position_invalid(
    mock_device, caplog: pytest.LogCaptureFixture
) -> None:
    """Test invalid position returns None."""
    entity = RyseCoverEntity(mock_device)
    entity._current_position = 200
    mock_device.is_valid_position.return_value = False

    pos = entity.current_cover_position
    assert pos is None
    assert "Invalid position" in caplog.text
