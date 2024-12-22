"""Tests for the Schlage integration."""

from typing import Any
from unittest.mock import Mock, create_autospec, patch

from freezegun.api import FrozenDateTimeFactory
from pycognito.exceptions import WarrantException
from pyschlage.exceptions import Error, NotAuthorizedError
from pyschlage.lock import Lock
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.schlage.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceRegistry

from . import MockSchlageConfigEntry

from tests.common import async_fire_time_changed


@patch(
    "pyschlage.Auth",
    side_effect=WarrantException,
)
async def test_auth_failed(
    mock_auth: Mock, hass: HomeAssistant, mock_config_entry: MockSchlageConfigEntry
) -> None:
    """Test failed auth on setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_auth.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_update_data_fails(
    hass: HomeAssistant,
    mock_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
) -> None:
    """Test that we properly handle API errors."""
    mock_schlage.locks.side_effect = Error
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_schlage.locks.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_data_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
) -> None:
    """Test that we properly handle API errors."""
    mock_schlage.locks.side_effect = NotAuthorizedError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_schlage.locks.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_update_data_get_logs_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
    mock_lock: Mock,
) -> None:
    """Test that we properly handle API errors."""
    mock_schlage.locks.return_value = [mock_lock]
    mock_lock.logs.reset_mock()
    mock_lock.logs.side_effect = NotAuthorizedError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_schlage.locks.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockSchlageConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
) -> None:
    """Test the Schlage configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_lock_device_registry(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: MockSchlageConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test lock is added to device registry."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert device == snapshot


async def test_auto_add_device(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_schlage: Mock,
    mock_lock: Mock,
    mock_lock_attrs: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are auto-added to the device registry."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert device is not None
    all_devices = dr.async_entries_for_config_entry(
        device_registry, mock_added_config_entry.entry_id
    )
    assert len(all_devices) == 1

    mock_lock_attrs["device_id"] = "test2"
    new_mock_lock = create_autospec(Lock)
    new_mock_lock.configure_mock(**mock_lock_attrs)
    mock_schlage.locks.return_value = [mock_lock, new_mock_lock]

    # Make the coordinator refresh data.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    new_device = device_registry.async_get_device(identifiers={(DOMAIN, "test2")})
    assert new_device is not None

    all_devices = dr.async_entries_for_config_entry(
        device_registry, mock_added_config_entry.entry_id
    )
    assert len(all_devices) == 2


async def test_auto_remove_device(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: MockSchlageConfigEntry,
    mock_schlage: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are auto-added to the device registry."""
    assert device_registry.async_get_device(identifiers={(DOMAIN, "test")}) is not None

    mock_schlage.locks.return_value = []

    # Make the coordinator refresh data.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device(identifiers={(DOMAIN, "test")}) is None
    all_devices = dr.async_entries_for_config_entry(
        device_registry, mock_added_config_entry.entry_id
    )
    assert len(all_devices) == 0
