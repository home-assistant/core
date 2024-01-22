"""Tests for init module."""
from unittest.mock import patch

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_async_setup_raises_entry_not_ready(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    config_entry = mock_config_entry
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError("API unavailable"),
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
