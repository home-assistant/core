"""Tests for the energieleser integration setup and unload."""

from unittest.mock import AsyncMock

from energieleser import (
    EnergieleserConnectionError,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry sets up and unloads cleanly."""
    mock_stromleser_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the device is unreachable."""
    mock_energieleser_client.get_device.side_effect = EnergieleserConnectionError(
        "boom"
    )
    mock_stromleser_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_stromleser_config_entry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_unknown_device_error(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the device type is unknown/malformed during setup."""
    mock_energieleser_client.get_device.side_effect = EnergieleserUnknownDeviceError(
        "unknown"
    )
    mock_stromleser_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_stromleser_config_entry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_generic_error(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when a generic library error occurs during setup."""
    mock_energieleser_client.get_device.side_effect = EnergieleserError("generic")
    mock_stromleser_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_stromleser_config_entry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.SETUP_RETRY
