"""Tests for the Podcast Player integration setup."""

from unittest.mock import AsyncMock

from aiopodcast import InvalidFeedError, PodcastConnectionError

from homeassistant.components.podcast_player.coordinator import PodcastUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test setting up a podcast feed."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, PodcastUpdateCoordinator)
    mock_client.async_fetch.assert_awaited_once()


async def test_setup_retries_when_feed_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test retrying setup when the feed is unavailable."""
    mock_client.async_fetch.side_effect = PodcastConnectionError("Connection failed")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_for_invalid_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test failing setup for a permanently invalid feed."""
    mock_client.async_fetch.side_effect = InvalidFeedError("Invalid feed")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading a podcast feed."""
    assert hass.states.get("event.example_podcast") is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get("event.example_podcast")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
