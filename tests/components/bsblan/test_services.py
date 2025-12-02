"""Tests for the BSB-Lan services."""

from unittest.mock import MagicMock

from bsblan import BSBLANError, DeviceTime
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_sync_time_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sync_time service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock device time that differs from HA time
    mock_bsblan.time.return_value = DeviceTime.from_json(
        '{"time": {"name": "Time", "value": "01.01.2020 00:00:00", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}'
    )

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        "sync_time",
        {"config_entry_id": mock_config_entry.entry_id},
        blocking=True,
    )

    # Verify time() was called to check current device time
    assert mock_bsblan.time.called

    # Verify set_time() was called with current HA time
    current_time_str = dt_util.now().strftime("%d.%m.%Y %H:%M:%S")
    mock_bsblan.set_time.assert_called_once_with(current_time_str)


async def test_sync_time_service_no_update_when_same(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sync_time service doesn't update when time matches."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock device time that matches HA time
    current_time_str = dt_util.now().strftime("%d.%m.%Y %H:%M:%S")
    mock_bsblan.time.return_value = DeviceTime.from_json(
        f'{{"time": {{"name": "Time", "value": "{current_time_str}", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}}}'
    )

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        "sync_time",
        {"config_entry_id": mock_config_entry.entry_id},
        blocking=True,
    )

    # Verify time() was called
    assert mock_bsblan.time.called

    # Verify set_time() was NOT called since times match
    assert not mock_bsblan.set_time.called


async def test_sync_time_service_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the sync_time service handles errors gracefully."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock time() to raise an error
    mock_bsblan.time.side_effect = BSBLANError("Connection failed")

    # Call the service - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to sync time"):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"config_entry_id": mock_config_entry.entry_id},
            blocking=True,
        )


async def test_sync_time_service_set_time_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the sync_time service handles set_time errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock device time that differs
    mock_bsblan.time.return_value = DeviceTime.from_json(
        '{"time": {"name": "Time", "value": "01.01.2020 00:00:00", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}'
    )

    # Mock set_time() to raise an error
    mock_bsblan.set_time.side_effect = BSBLANError("Write failed")

    # Call the service - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to sync time"):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"config_entry_id": mock_config_entry.entry_id},
            blocking=True,
        )


async def test_sync_time_service_entry_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the sync_time service raises error for non-existent entry."""
    # Set up the entry (this registers the service)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Call the service with a non-existent entry ID
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"config_entry_id": "non_existent_entry_id"},
            blocking=True,
        )


async def test_sync_time_service_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the sync_time service raises error for unloaded entry."""
    # Set up the first entry (this registers the service)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a second unloaded entry
    unloaded_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unloaded BSBLAN",
        data=mock_config_entry.data.copy(),
        unique_id="unloaded_unique_id",
    )
    unloaded_entry.add_to_hass(hass)
    # Don't call async_setup on this entry, so it stays NOT_LOADED

    # Call the service with the unloaded entry ID - should raise error
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"config_entry_id": unloaded_entry.entry_id},
            blocking=True,
        )
