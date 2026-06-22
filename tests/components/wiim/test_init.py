"""Tests for the WiiM integration initialization."""

from unittest.mock import AsyncMock, patch

import pytest
from wiim.exceptions import WiimDeviceException, WiimRequestException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    mock_wiim_controller: AsyncMock,
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (WiimDeviceException("device init failed"), ConfigEntryState.SETUP_RETRY),
        (WiimRequestException("http failure"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_raises_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_controller: AsyncMock,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test that setup raises ConfigEntryNotReady on device/request exceptions."""
    with patch(
        "homeassistant.components.wiim.async_create_wiim_device",
        side_effect=exc,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_setup_raises_config_entry_not_ready_when_no_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    mock_wiim_controller: AsyncMock,
) -> None:
    """Test setup raises ConfigEntryNotReady when no internal URL is configured."""
    # Do NOT call async_process_ha_core_config so get_url raises NoURLAvailableError.
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_url_after_core_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    mock_wiim_controller: AsyncMock,
) -> None:
    """Test that setup succeeds once internal_url is configured."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://192.168.1.10:8123"}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
