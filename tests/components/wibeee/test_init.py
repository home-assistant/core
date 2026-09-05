"""Tests for Wibeee integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp
import pytest

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_loaded(loaded_entry: ConfigEntry) -> None:
    """Test that config entry is loaded."""
    assert loaded_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady on connection error."""
    mock_wibeee_api.async_fetch_device_info.side_effect = aiohttp.ClientError("boom")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_device_info_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test setup retries when the device returns no device info."""
    mock_config_entry.add_to_hass(hass)
    mock_wibeee_api.async_fetch_device_info.return_value = None

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(TimeoutError("timeout"), id="timeout"),
        pytest.param(aiohttp.ClientError("boom"), id="client_error"),
    ],
)
async def test_setup_entry_initial_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
    side_effect: Exception,
) -> None:
    """Test setup raises ConfigEntryNotReady when the initial fetch fails."""
    mock_wibeee_api.async_fetch_sensors_data.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_unexpected_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test setup fails permanently when another device answers at the host."""
    mock_wibeee_api.async_fetch_device_info.return_value.mac_addr_formatted = (
        "ffeeddccbbaa"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_no_initial_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady when initial data is None."""
    mock_wibeee_api.async_fetch_sensors_data.return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test that unloading works."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
