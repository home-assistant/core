"""Tests for the Mammotion integration setup."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pymammotion.data.model.device import MowingDevice
from Tea.exceptions import UnretryableException

from homeassistant.components.mammotion.config import SAVE_DELAY
from homeassistant.components.mammotion.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DEFAULT_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_mower_api.mammotion.stop.assert_awaited_once()
    mock_mower_api.mammotion.remove_device.assert_awaited_once_with(DEFAULT_NAME)


async def test_setup_retry_on_failed_refresh(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the first data fetch fails."""
    mock_mower_api.update.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the cloud is unreachable."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = (
        ClientConnectorError(Mock(), OSError("boom"))
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_state_restored_from_store(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the stored mower state is restored into the library on setup."""
    handle = Mock()
    mock_mower_api.mammotion.mower.return_value = handle
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 0,
        "key": storage_key,
        "data": {DEFAULT_NAME: MowingDevice().to_dict()},
    }

    await setup_integration(hass, mock_config_entry)

    handle.restore_device.assert_called_once()


async def test_state_persisted_after_delay(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test mower state is not written on every poll but after the save delay."""
    await setup_integration(hass, mock_config_entry)
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"

    assert storage_key not in hass_storage

    freezer.tick(timedelta(seconds=SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert DEFAULT_NAME in hass_storage[storage_key]["data"]


async def test_state_persisted_on_unload(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test pending mower state is flushed when the entry is unloaded."""
    await setup_integration(hass, mock_config_entry)
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"

    assert storage_key not in hass_storage

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DEFAULT_NAME in hass_storage[storage_key]["data"]


async def test_remove_entry_keeps_other_entry_state(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test removing an entry leaves the stored state of other entries intact."""
    other_key = f"{DOMAIN}.other_entry_id"
    hass_storage[other_key] = {
        "version": 1,
        "minor_version": 0,
        "key": other_key,
        "data": {"Luba-OTHER": MowingDevice().to_dict()},
    }
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert f"{DOMAIN}.{mock_config_entry.entry_id}" not in hass_storage
    assert other_key in hass_storage


async def test_setup_error_on_unretryable_error(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry errors out on an unretryable login failure."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = (
        UnretryableException(Mock(), OSError("boom"))
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
