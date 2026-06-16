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


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(EnergieleserConnectionError("boom"), id="connection_error"),
        pytest.param(
            EnergieleserUnknownDeviceError("unknown"), id="unknown_device_error"
        ),
        pytest.param(EnergieleserError("generic"), id="generic_error"),
    ],
)
async def test_setup_retries_on_client_error(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test the entry is retried when the client raises an error during setup."""
    mock_energieleser_client.get_device.side_effect = side_effect
    mock_stromleser_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_stromleser_config_entry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.SETUP_RETRY
