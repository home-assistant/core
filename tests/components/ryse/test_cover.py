"""Test RYSE Cover entity behavior."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.components.ryse.const import DOMAIN
from homeassistant.components.ryse.cover import RyseCoverEntity

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a minimal mock ConfigEntry."""
    return MockConfigEntry(
        domain="ryse", title="Test Device", data={}, unique_id="AA:BB:CC:DD:EE:FF"
    )


@pytest.fixture
def mock_device() -> MagicMock:
    """Mock RyseBLEDevice."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.is_valid_position.return_value = True
    device.get_real_position.side_effect = lambda x: x
    device.is_closed.side_effect = lambda x: x == 0
    return device


async def test_cover_properties(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test properties of RyseCoverEntity."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    info = entity.device_info
    assert info["manufacturer"] == "RYSE"
    assert (DOMAIN, "AA:BB:CC:DD:EE:FF") in info["identifiers"]
    assert entity._attr_supported_features & CoverEntityFeature.OPEN


async def test_update_position_valid(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating position calls HA state write."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity.async_write_ha_state = MagicMock()

    await entity._update_position(50)
    mock_device.is_valid_position.assert_called_with(50)
    entity.async_write_ha_state.assert_called()


async def test_async_open_close_and_set_cover(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test open, close and set cover methods."""
    mock_device.send_open = AsyncMock()
    mock_device.send_close = AsyncMock()
    mock_device.send_set_position = AsyncMock()
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    await entity.async_open_cover()
    await entity.async_close_cover()
    await entity.async_set_cover_position(**{ATTR_POSITION: 75})

    mock_device.send_open.assert_awaited()
    mock_device.send_close.assert_awaited()
    mock_device.send_set_position.assert_awaited()


async def test_async_update_handles_exceptions(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test BLE communication errors handled gracefully."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    mock_device.client = None
    mock_device.pair = AsyncMock(return_value=False)

    await entity.async_update()
    assert entity._attr_available is False


async def test_current_cover_position_invalid(
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test invalid position returns None."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity._current_position = 200
    mock_device.is_valid_position.return_value = False

    pos = entity.current_cover_position
    assert pos is None
    assert "Invalid position" in caplog.text


async def test_async_update_connected_triggers_available_and_get_position(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Covers: `self._attr_available = True` and `send_get_position()`."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    # Mock as connected
    mock_device.client = MagicMock()
    mock_device.client.is_connected = True

    # Mock get_position behavior
    mock_device.send_get_position = AsyncMock()

    entity._current_position = None  # triggers send_get_position()

    await entity.async_update()

    assert entity._attr_available is True
    mock_device.send_get_position.assert_awaited_once()


async def test_async_update_timeout_error(
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Covers: `except TimeoutError` block."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    mock_device.client = MagicMock()
    mock_device.client.is_connected = True

    mock_device.send_get_position = AsyncMock(side_effect=TimeoutError())

    await entity.async_update()

    mock_device.send_get_position.assert_awaited_once()
    assert "BLE communication error while reading device data" in caplog.text
    assert entity.available is False


async def test_async_update_generic_exception(
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Covers: `except Exception` block."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    mock_device.client = MagicMock()
    mock_device.client.is_connected = True

    mock_device.send_get_position = AsyncMock(side_effect=Exception("boom"))

    await entity.async_update()

    mock_device.send_get_position.assert_awaited_once()
    assert "Unexpected error while reading device data" in caplog.text
    assert entity.available is False


async def test_current_cover_position_valid(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Covers final line: `return self._current_position`."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity._current_position = 42

    mock_device.is_valid_position.return_value = True

    assert entity.current_cover_position == 42


async def test_entity_lifecycle(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_added_to_hass, async_will_remove_from_hass and _clear_callback."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    # Mock async_on_remove to check registration
    entity.async_on_remove = MagicMock()

    # Call added_to_hass
    await entity.async_added_to_hass()
    assert mock_device.update_callback == entity._update_position
    entity.async_on_remove.assert_called_once_with(entity._clear_callback)

    # Call will_remove_from_hass
    await entity.async_will_remove_from_hass()
    assert mock_device.update_callback is None


async def test_clear_callback_other_callback(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test _clear_callback does not clear if callback is different."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    other_cb = MagicMock()
    mock_device.update_callback = other_cb

    entity._clear_callback()
    assert mock_device.update_callback == other_cb


async def test_async_update_pairing_success(
    mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_update when pairing succeeds."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    mock_device.client = None
    mock_device.pair = AsyncMock(return_value=True)
    mock_device.send_get_position = AsyncMock()

    await entity.async_update()
    assert entity.available is True
    mock_device.send_get_position.assert_awaited_once()


async def test_async_update_pairing_failure_log_debug(
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test debug log when pairing fails and entity was available."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity._attr_available = True
    mock_device.client = None
    mock_device.pair = AsyncMock(return_value=False)
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.ryse.cover")

    await entity.async_update()
    assert entity.available is False
    assert "Failed to pair with device, skipping update" in caplog.text


async def test_async_update_pairing_failure_no_log_debug(
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no debug log when pairing fails and entity was not available."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity._attr_available = False
    mock_device.client = None
    mock_device.pair = AsyncMock(return_value=False)
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.ryse.cover")

    await entity.async_update()
    assert entity.available is False
    assert "Failed to pair with device, skipping update" not in caplog.text
