"""Test the OpenDisplay integration setup and unload."""

from unittest.mock import AsyncMock, patch

from opendisplay import (
    BLEConnectionError,
    BLETimeoutError,
    GlobalConfig,
    OpenDisplayError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import DEVICE_CONFIG, FIRMWARE_VERSION

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_device_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when device is not visible."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.opendisplay.async_ble_device_from_address",
        return_value=None,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        BLEConnectionError("connection failed"),
        BLETimeoutError("timeout"),
        OpenDisplayError("device error"),
    ],
)
async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test setup retries on BLE connection errors."""
    mock_config_entry.add_to_hass(hass)

    mock_device = AsyncMock()
    mock_device.__aenter__ = AsyncMock(side_effect=exception)
    mock_device.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "homeassistant.components.opendisplay.OpenDisplayDevice",
        return_value=mock_device,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_runtime_data_populated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that runtime data is populated after setup."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.firmware == FIRMWARE_VERSION
    assert isinstance(mock_config_entry.runtime_data.device_config, GlobalConfig)
    assert mock_config_entry.runtime_data.device_config is DEVICE_CONFIG
