"""Tests for the Mastodon integration."""

from unittest.mock import AsyncMock

from mastodon.Mastodon import MastodonError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_initialization_failure(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test initialization failure."""
    mock_mastodon_client.instance.side_effect = MastodonError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
