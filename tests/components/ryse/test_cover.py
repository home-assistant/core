"""Test RYSE Cover entity behavior."""

import logging
from unittest.mock import AsyncMock, MagicMock

from bleak import BleakError
import pytest

from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.components.ryse.const import DOMAIN
from homeassistant.components.ryse.cover import RyseCoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
    device.get_real_position.side_effect = lambda x: 100 - x
    device.is_closed.side_effect = lambda x: x == 100
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
    """Test updating position calls HA state write and stores correct values."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity.async_write_ha_state = MagicMock()

    # Simulate device reporting raw position 100 (fully closed)
    await entity._update_position(100)
    mock_device.is_valid_position.assert_called_with(100)
    # _current_position must be the mapped HA display position (100 - 100 = 0)
    assert entity._current_position == 0
    # is_closed must receive the raw device position (100), not the HA position
    mock_device.is_closed.assert_called_with(100)
    assert entity._attr_is_closed is True
    entity.async_write_ha_state.assert_called()


async def test_async_open_close_and_set_cover(
    hass: HomeAssistant, mock_device: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test open, close and set cover methods."""
    mock_device.send_open = AsyncMock()
    mock_device.send_close = AsyncMock()
    mock_device.send_set_position = AsyncMock()
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()

    await entity.async_open_cover()
    await entity.async_close_cover()

    ha_position = 75
    await entity.async_set_cover_position(**{ATTR_POSITION: ha_position})

    mock_device.send_open.assert_awaited()
    mock_device.send_close.assert_awaited()
    # Device receives the inverted (raw) position, not the HA display value
    mock_device.send_set_position.assert_awaited_once_with(100 - ha_position)
    # Entity remembers the HA display position so current_cover_position reports correctly
    assert entity._current_position == ha_position


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
    caplog.set_level(logging.WARNING, logger="homeassistant.components.ryse.cover")

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
    caplog.set_level(logging.WARNING, logger="homeassistant.components.ryse.cover")

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
    caplog.set_level(logging.ERROR, logger="homeassistant.components.ryse.cover")

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
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_added_to_hass, async_will_remove_from_hass and _clear_callback."""
    entity = RyseCoverEntity(mock_device, mock_config_entry)

    # Attach hass so base-class async_added_to_hass() can run without errors
    entity.hass = hass

    # Spy on async_on_remove to check registration while preserving base behavior
    original_on_remove = entity.async_on_remove
    entity.async_on_remove = MagicMock(side_effect=original_on_remove)

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


# ---------------------------------------------------------------------------
# Exception-handling tests for BLE command methods
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("t/o"), OSError("io err"), BleakError("ble err")],
    ids=["timeout", "oserror", "bleak"],
)
async def test_async_open_cover_ble_error_raises_ha_error(
    exc: Exception,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """BLE errors during send_open are re-raised as HomeAssistantError."""
    mock_device.send_open = AsyncMock(side_effect=exc)
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity.async_write_ha_state = MagicMock()
    original_position = entity._current_position

    with pytest.raises(HomeAssistantError, match="Failed to open cover"):
        await entity.async_open_cover()

    # State must NOT be updated on failure
    assert entity._current_position == original_position
    entity.async_write_ha_state.assert_not_called()


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("t/o"), OSError("io err"), BleakError("ble err")],
    ids=["timeout", "oserror", "bleak"],
)
async def test_async_close_cover_ble_error_raises_ha_error(
    exc: Exception,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """BLE errors during send_close are re-raised as HomeAssistantError."""
    mock_device.send_close = AsyncMock(side_effect=exc)
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity.async_write_ha_state = MagicMock()
    original_position = entity._current_position

    with pytest.raises(HomeAssistantError, match="Failed to close cover"):
        await entity.async_close_cover()

    # State must NOT be updated on failure
    assert entity._current_position == original_position
    entity.async_write_ha_state.assert_not_called()


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("t/o"), OSError("io err"), BleakError("ble err")],
    ids=["timeout", "oserror", "bleak"],
)
async def test_async_set_cover_position_ble_error_raises_ha_error(
    exc: Exception,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """BLE errors during send_set_position are re-raised as HomeAssistantError."""
    mock_device.send_set_position = AsyncMock(side_effect=exc)
    entity = RyseCoverEntity(mock_device, mock_config_entry)
    entity.async_write_ha_state = MagicMock()
    original_position = entity._current_position

    with pytest.raises(HomeAssistantError, match="Failed to set cover position"):
        await entity.async_set_cover_position(**{ATTR_POSITION: 50})

    # State must NOT be updated on failure
    assert entity._current_position == original_position
    entity.async_write_ha_state.assert_not_called()
