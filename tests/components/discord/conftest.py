"""Discord integration test fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest

from homeassistant.core import HomeAssistant

from . import CHANNEL_ID, create_entry

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a pre-configured Discord config entry (with one channel subentry)."""
    return create_entry(hass)


@pytest.fixture
def mock_channel() -> MagicMock:
    """Return a mock nextcord TextChannel."""
    channel = MagicMock()
    channel.id = CHANNEL_ID
    channel.name = "general"
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def mock_discord_bot(mock_channel: MagicMock) -> Generator[MagicMock]:
    """Patch nextcord.Client used in __init__ and notify."""
    bot = MagicMock(spec=nextcord.Client)
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(return_value=mock_channel)
    bot.fetch_user = AsyncMock(side_effect=nextcord.NotFound(MagicMock(), ""))

    with (
        patch(
            "homeassistant.components.discord.__init__.nextcord.Client",
            return_value=bot,
        ),
        patch(
            "homeassistant.components.discord.notify.nextcord.Client",
            return_value=bot,
        ),
    ):
        yield bot


@pytest.fixture
async def setup_discord(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discord_bot: MagicMock,
) -> None:
    """Set up the Discord integration."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
