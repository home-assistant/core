"""Tests for the saj integration initialization."""

import pysaj
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import PySajMocks

from tests.common import MockConfigEntry


async def test_setup_entry_ethernet(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: PySajMocks,
) -> None:
    """Test async_setup_entry for ethernet connection."""
    entry = await setup_integration(hass, mock_config_entry_ethernet)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_wifi(
    hass: HomeAssistant,
    mock_config_entry_wifi: MockConfigEntry,
    mock_pysaj: PySajMocks,
) -> None:
    """Test async_setup_entry for wifi connection."""
    entry = await setup_integration(hass, mock_config_entry_wifi)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: PySajMocks,
) -> None:
    """Test async_setup_entry handles connection failures."""
    mock_pysaj.saj.read.return_value = False
    entry = await setup_integration(hass, mock_config_entry_ethernet)
    # Entry should be in SETUP_RETRY state when setup fails
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry_wifi: MockConfigEntry,
    mock_pysaj: PySajMocks,
) -> None:
    """Test async_setup_entry fails WiFi auth at setup without endless retries."""
    mock_pysaj.saj.read.side_effect = pysaj.UnauthorizedException("Auth failed")
    entry = await setup_integration(hass, mock_config_entry_wifi)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_ethernet_unauthorized_retries(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: PySajMocks,
) -> None:
    """Ethernet UnauthorizedException is treated as not ready (e.g. wrong type)."""
    mock_pysaj.saj.read.side_effect = pysaj.UnauthorizedException("unexpected")
    entry = await setup_integration(hass, mock_config_entry_ethernet)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        Exception("Unexpected error"),
        RuntimeError("Unexpected runtime error"),
    ],
)
async def test_setup_entry_unexpected_error(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: PySajMocks,
    exception: Exception,
) -> None:
    """Test async_setup_entry handles unexpected errors."""
    mock_pysaj.saj.read.side_effect = exception
    entry = await setup_integration(hass, mock_config_entry_ethernet)
    # Truly unexpected exceptions should result in SETUP_ERROR
    # so the actual error is visible rather than being hidden
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
    mock_pysaj: PySajMocks,
) -> None:
    """Test async_unload_entry."""
    entry = await setup_integration(hass, mock_config_entry_ethernet)

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
