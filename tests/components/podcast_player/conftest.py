"""Fixtures for the Podcast Player integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiopodcast import Podcast, PodcastClient, PodcastEnclosure, PodcastEpisode
import pytest

from homeassistant.components.podcast_player import PodcastConfigEntry
from homeassistant.components.podcast_player.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_URL = "https://example.com/feed.xml"
TEST_CANONICAL_URL = "https://cdn.example.com/podcast.xml"


@pytest.fixture
def podcast() -> Podcast:
    """Return a podcast feed."""
    return Podcast(
        source_url=TEST_URL,
        canonical_url=TEST_CANONICAL_URL,
        title="Example Podcast",
        description="An example podcast",
        author="Example Author",
        website_url="https://example.com/podcast",
        artwork_url="https://example.com/podcast.jpg",
        episodes=(
            PodcastEpisode(
                title="First episode",
                guid="episode-one",
                description="The first episode",
                published=datetime(2026, 8, 1, tzinfo=UTC),
                duration_seconds=1800,
                artwork_url="https://example.com/episode.jpg",
                website_url="https://example.com/episodes/one",
                enclosure=PodcastEnclosure(
                    url="https://cdn.example.com/episode.mp3",
                    mime_type="audio/mpeg",
                    length=123456,
                ),
            ),
        ),
    )


@pytest.fixture
def mock_client(podcast: Podcast) -> Generator[AsyncMock]:
    """Return a mocked podcast client."""
    client = MagicMock(spec=PodcastClient)
    client.async_fetch = AsyncMock(return_value=podcast)
    with patch(
        "homeassistant.components.podcast_player.client.PodcastClient",
        return_value=client,
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked podcast config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Example Podcast",
        data={CONF_URL: TEST_URL},
        unique_id=TEST_CANONICAL_URL,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a podcast config entry."""
    with patch(
        "homeassistant.components.podcast_player.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> PodcastConfigEntry:
    """Set up the Podcast Player integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry
