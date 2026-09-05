"""Tests for LANBON setup and unload."""

from unittest.mock import AsyncMock, patch

from aiolanbon import LanbonAuthError, LanbonConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import gateway_info

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the integration loads and unloads."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the token is rejected."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info",
            new=AsyncMock(side_effect=LanbonAuthError("unauthorized")),
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_devices",
            new=AsyncMock(side_effect=LanbonAuthError("unauthorized")),
        ),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the device is unreachable."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_info",
            new=AsyncMock(return_value=gateway_info()),
        ),
        patch(
            "homeassistant.components.lanbon.LanbonClient.get_devices",
            new=AsyncMock(side_effect=LanbonConnectionError("down")),
        ),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
