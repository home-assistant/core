"""Tests for the Lunatone integration."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import BASE_URL, VERSION, setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == "Lunatone"
    assert device_entry.sw_version == VERSION
    assert device_entry.configuration_url == BASE_URL

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready_cause_of_info_object(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_info.async_update.side_effect = aiohttp.ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_lunatone_info.async_update.side_effect = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lunatone_info.async_update.assert_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_cause_of_devices_object(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_devices.async_update.side_effect = aiohttp.ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    mock_lunatone_devices.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_lunatone_devices.async_update.side_effect = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lunatone_info.async_update.assert_called()
    mock_lunatone_devices.async_update.assert_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_no_info_data(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_info.data = None

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_no_devices_data(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_devices.data = None

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    mock_lunatone_devices.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_no_serial_number(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_info.serial_number = None

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
