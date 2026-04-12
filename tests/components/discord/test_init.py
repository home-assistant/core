"""Test the Discord integration setup and unload."""

from unittest.mock import AsyncMock, MagicMock, patch

import nextcord

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import BOT_ID, BOT_NAME, CONF_DATA

from tests.common import MockConfigEntry


def _patch_init_bot(login_side_effect=None):
    """Patch nextcord.Client for __init__ setup."""
    bot = MagicMock(spec=nextcord.Client)
    bot.login = AsyncMock(side_effect=login_side_effect)
    bot.close = AsyncMock()
    return patch(
        "homeassistant.components.discord.__init__.nextcord.Client",
        return_value=bot,
    )


async def test_setup_entry(
    hass: HomeAssistant,
    setup_discord: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry is set up successfully."""
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    setup_discord: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry is unloaded cleanly."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_invalid_auth(hass: HomeAssistant) -> None:
    """Test that an invalid token raises ConfigEntryAuthFailed."""
    entry = MockConfigEntry(
        domain="discord",
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_bot(login_side_effect=nextcord.LoginFailure):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a connection error raises ConfigEntryNotReady."""
    entry = MockConfigEntry(
        domain="discord",
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_bot(login_side_effect=nextcord.HTTPException(MagicMock(), "")):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
