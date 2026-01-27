"""Tests for the NRGkick integration initialization."""

from __future__ import annotations

from nrgkick_api import (
    NRGkickAuthenticationError as LibAuthError,
    NRGkickConnectionError as LibConnectionError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import async_setup_integration, create_mock_config_entry

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nrgkick_api
) -> None:
    """Test successful setup of entry."""
    await async_setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_failed_connection(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nrgkick_api
) -> None:
    """Test setup entry with failed connection."""
    mock_config_entry.add_to_hass(hass)

    mock_nrgkick_api.get_info.side_effect = LibConnectionError("Connection failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nrgkick_api
) -> None:
    """Test successful unload of entry."""
    await async_setup_integration(hass, mock_config_entry)

    # Use the config_entries.async_unload for proper state management
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test successful coordinator update."""
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    # Use proper setup to set entry state
    await async_setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
    assert coordinator.data.info == mock_info_data
    assert coordinator.data.control == mock_control_data
    assert coordinator.data.values == mock_values_data


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_nrgkick_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test coordinator update failed."""
    entry = create_mock_config_entry(data={CONF_HOST: "192.168.1.100"})
    mock_nrgkick_api.get_values.side_effect = LibConnectionError("Connection failed")

    await async_setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_failed(
    hass: HomeAssistant, mock_nrgkick_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test coordinator auth failed."""
    entry = create_mock_config_entry(data={CONF_HOST: "192.168.1.100"})
    mock_nrgkick_api.get_values.side_effect = LibAuthError("Auth failed")

    await async_setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY
