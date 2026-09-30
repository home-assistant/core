"""Tests for the saj integration initialization."""

from unittest.mock import MagicMock

import pysaj
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("connection_method", ["ethernet", "wifi"], indirect=True)
@pytest.mark.usefixtures("mock_pysaj_saj")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry for ethernet and wifi connections."""
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test async_setup_entry handles connection failures."""
    mock_pysaj_saj.read.return_value = False
    entry = await setup_integration(hass, mock_config_entry)
    # Entry should be in SETUP_RETRY state when setup fails
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("connection_method", ["wifi"], indirect=True)
async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test async_setup_entry fails WiFi auth at setup without endless retries."""
    mock_pysaj_saj.read.side_effect = pysaj.UnauthorizedException("Auth failed")
    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            pysaj.UnauthorizedException("unexpected"), id="ethernet_unauthorized"
        ),
        pytest.param(
            pysaj.UnexpectedResponseException("bad response"), id="unexpected_response"
        ),
        pytest.param(TimeoutError("timed out"), id="timeout"),
        pytest.param(OSError("network unreachable"), id="os_error"),
        pytest.param(Exception("Unexpected error"), id="unexpected"),
        pytest.param(RuntimeError("Unexpected runtime error"), id="runtime_error"),
    ],
)
async def test_setup_entry_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
    exception: Exception,
) -> None:
    """Test errors during setup result in a retry."""
    mock_pysaj_saj.read.side_effect = exception
    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_pysaj_saj")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry."""
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
