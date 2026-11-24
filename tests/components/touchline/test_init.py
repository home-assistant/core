"""Tests for the Touchline integration setup."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytouchline_extended import TouchlineConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("get_number_of_devices", id="number-of-devices"),
        pytest.param("update", id="device-update"),
    ],
)
async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pytouchline: MagicMock,
    method: str,
) -> None:
    """Test setup is retried when the controller cannot be reached."""
    getattr(mock_pytouchline, method).side_effect = TouchlineConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("get_controller_id", id="controller-id"),
        pytest.param("get_device_id", id="device-id"),
    ],
)
async def test_setup_retry_on_missing_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pytouchline: MagicMock,
    method: str,
) -> None:
    """Test setup is retried when the controller returns no ID for a device."""
    getattr(mock_pytouchline, method).return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
