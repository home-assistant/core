"""Tests for RYSE init setup."""

from unittest.mock import MagicMock, patch

from bleak import BleakError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""
    assert setup_integration.state is ConfigEntryState.LOADED
    mock_device.pair.assert_awaited_once()

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_device.unpair.assert_awaited_once()


async def test_setup_passes_resolved_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ryse_ble_device: MagicMock,
) -> None:
    """Test setup passes the Home Assistant-resolved BLEDevice to ryseble."""
    ble_device = MagicMock()
    with patch(
        "homeassistant.components.ryse.async_ble_device_from_address",
        return_value=ble_device,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ryse_ble_device.assert_called_once_with(ble_device)


async def test_setup_without_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the device is not seen by the bluetooth stack."""
    with patch(
        "homeassistant.components.ryse.async_ble_device_from_address",
        return_value=None,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_pairing_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Test setup is retried when pairing with the device fails."""
    mock_device.pair.return_value = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.unpair.assert_awaited_once()


async def test_setup_retries_on_ble_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Test setup is retried when pairing raises a BLE error."""
    mock_device.pair.side_effect = BleakError("ble err")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.unpair.assert_awaited_once()
