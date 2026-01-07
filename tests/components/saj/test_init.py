"""Tests for the saj integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pysaj

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry_ethernet(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
) -> None:
    """Test async_setup_entry for ethernet connection."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = "TEST123"
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            entry = await setup_integration(hass, mock_config_entry_ethernet)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_wifi(
    hass: HomeAssistant,
    mock_config_entry_wifi: MockConfigEntry,
) -> None:
    """Test async_setup_entry for wifi connection."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = "TEST123"
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            entry = await setup_integration(hass, mock_config_entry_wifi)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
) -> None:
    """Test async_setup_entry handles connection failures."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(return_value=False)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            entry = await setup_integration(hass, mock_config_entry_ethernet)
            # Entry should be in SETUP_RETRY state when setup fails
            assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry_wifi: MockConfigEntry,
) -> None:
    """Test async_setup_entry handles authentication failures."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnauthorizedException("Auth failed")
        )
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            entry = await setup_integration(hass, mock_config_entry_wifi)
            # Entry should be in SETUP_RETRY state when setup fails
            assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_unexpected_error(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
) -> None:
    """Test async_setup_entry handles unexpected errors."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(side_effect=Exception("Unexpected error"))
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            entry = await setup_integration(hass, mock_config_entry_ethernet)
            # Truly unexpected exceptions should result in SETUP_ERROR
            # so the actual error is visible rather than being hidden
            assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
) -> None:
    """Test async_unload_entry."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = "TEST123"
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            entry = await setup_integration(hass, mock_config_entry_ethernet)

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
