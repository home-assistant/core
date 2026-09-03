"""Tests for the Podcast Player media source."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from aiopodcast import Podcast, PodcastConnectionError, PodcastEnclosure
import pytest

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import MediaSourceItem, Unresolvable
from homeassistant.components.podcast_player import PodcastConfigEntry
from homeassistant.components.podcast_player.const import DOMAIN, MAX_BROWSE_EPISODES
from homeassistant.components.podcast_player.media_source import async_get_media_source
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_browse_podcasts_and_episodes(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test browsing configured podcasts and episodes."""
    source = await async_get_media_source(hass)

    root = await source.async_browse_media(MediaSourceItem(hass, DOMAIN, "", None))

    assert root.title == "Podcasts"
    assert root.children_media_class is MediaClass.PODCAST
    assert root.children is not None
    assert len(root.children) == 1
    podcast_item = root.children[0]
    assert podcast_item.title == "Example Podcast"
    assert podcast_item.identifier == init_integration.entry_id

    feed = await source.async_browse_media(
        MediaSourceItem(hass, DOMAIN, podcast_item.identifier, None)
    )

    assert feed.title == "Example Podcast"
    assert feed.children_media_class is MediaClass.EPISODE
    assert feed.not_shown == 0
    assert feed.children is not None
    assert len(feed.children) == 1
    episode = feed.children[0]
    assert episode.title == "First episode"
    assert episode.can_play is True
    assert episode.can_expand is False
    assert episode.media_content_type == "audio/mpeg"
    assert episode.thumbnail == "https://example.com/episode.jpg"
    assert mock_client.async_fetch.await_count == 2


async def test_resolve_episode(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
) -> None:
    """Test resolving a podcast episode."""
    source = await async_get_media_source(hass)
    feed = await source.async_browse_media(
        MediaSourceItem(hass, DOMAIN, init_integration.entry_id, None)
    )
    assert feed.children is not None

    result = await source.async_resolve_media(
        MediaSourceItem(hass, DOMAIN, feed.children[0].identifier, None)
    )

    assert result.url == "https://cdn.example.com/episode.mp3"
    assert result.mime_type == "audio/mpeg"


async def test_resolve_episode_with_inferred_mime_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test inferring an episode MIME type from its URL."""
    enclosure = replace(
        podcast.episodes[0].enclosure,
        url="https://cdn.example.com/episode.mp3?token=secret#fragment",
        mime_type=None,
    )
    episode = replace(podcast.episodes[0], enclosure=enclosure)
    mock_client.async_fetch.return_value = replace(podcast, episodes=(episode,))
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    source = await async_get_media_source(hass)
    with patch(
        "homeassistant.components.podcast_player.media_source.mimetypes.guess_type",
        return_value=("audio/mpeg", None),
    ) as mock_guess_type:
        feed = await source.async_browse_media(
            MediaSourceItem(hass, DOMAIN, mock_config_entry.entry_id, None)
        )
        assert feed.children is not None
        result = await source.async_resolve_media(
            MediaSourceItem(hass, DOMAIN, feed.children[0].identifier, None)
        )

    assert result.mime_type == "audio/mpeg"
    mock_guess_type.assert_called_with("/episode.mp3")


async def test_browse_limits_episode_count(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test limiting large feed responses in the media browser."""
    episode = podcast.episodes[0]
    episodes = tuple(
        replace(
            episode,
            title=f"Episode {index}",
            guid=f"episode-{index}",
            enclosure=PodcastEnclosure(
                url=f"https://cdn.example.com/{index}.mp3",
                mime_type="audio/mpeg",
            ),
        )
        for index in range(MAX_BROWSE_EPISODES + 2)
    )
    mock_client.async_fetch.return_value = replace(podcast, episodes=episodes)
    source = await async_get_media_source(hass)

    feed = await source.async_browse_media(
        MediaSourceItem(hass, DOMAIN, init_integration.entry_id, None)
    )

    assert feed.children is not None
    assert len(feed.children) == MAX_BROWSE_EPISODES
    assert feed.not_shown == 2


async def test_browse_without_configured_feed(hass: HomeAssistant) -> None:
    """Test browsing without a configured podcast feed."""
    source = await async_get_media_source(hass)

    with pytest.raises(BrowseError) as error:
        await source.async_browse_media(MediaSourceItem(hass, DOMAIN, "", None))

    assert error.value.translation_key == "not_configured"


async def test_browse_with_only_unloaded_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing when the configured podcast feed is not loaded."""
    mock_config_entry.add_to_hass(hass)
    source = await async_get_media_source(hass)

    with pytest.raises(BrowseError) as error:
        await source.async_browse_media(MediaSourceItem(hass, DOMAIN, "", None))

    assert error.value.translation_key == "feed_unavailable"


async def test_browse_unloaded_feed(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
) -> None:
    """Test browsing a configured podcast feed that is not loaded."""
    unloaded_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unavailable Podcast",
        data={},
    )
    unloaded_entry.add_to_hass(hass)
    source = await async_get_media_source(hass)

    with pytest.raises(BrowseError) as error:
        await source.async_browse_media(
            MediaSourceItem(hass, DOMAIN, unloaded_entry.entry_id, None)
        )

    assert error.value.translation_key == "feed_unavailable"


@pytest.mark.parametrize("identifier", ["unknown", "unknown/path"])
async def test_browse_unknown_path(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    identifier: str,
) -> None:
    """Test browsing an unknown podcast path."""
    source = await async_get_media_source(hass)

    with pytest.raises(BrowseError) as error:
        await source.async_browse_media(MediaSourceItem(hass, DOMAIN, identifier, None))

    assert error.value.translation_key == "path_not_found"


async def test_browse_unavailable_feed(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test browsing a temporarily unavailable podcast feed."""
    mock_client.async_fetch.side_effect = PodcastConnectionError("Connection failed")
    source = await async_get_media_source(hass)

    with pytest.raises(BrowseError) as error:
        await source.async_browse_media(
            MediaSourceItem(hass, DOMAIN, init_integration.entry_id, None)
        )

    assert error.value.translation_key == "feed_unavailable"


async def test_resolve_unknown_episode(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
) -> None:
    """Test resolving an episode that no longer exists."""
    source = await async_get_media_source(hass)

    with pytest.raises(Unresolvable) as error:
        await source.async_resolve_media(
            MediaSourceItem(
                hass,
                DOMAIN,
                f"{init_integration.entry_id}/unknown",
                None,
            )
        )

    assert error.value.translation_key == "episode_unavailable"


async def test_resolve_unloaded_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resolving an episode from a feed that is not loaded."""
    mock_config_entry.add_to_hass(hass)
    source = await async_get_media_source(hass)

    with pytest.raises(Unresolvable) as error:
        await source.async_resolve_media(
            MediaSourceItem(
                hass,
                DOMAIN,
                f"{mock_config_entry.entry_id}/episode",
                None,
            )
        )

    assert error.value.translation_key == "feed_unavailable"


async def test_resolve_unavailable_feed(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test refreshing an unavailable feed while resolving a stale episode."""
    mock_client.async_fetch.side_effect = PodcastConnectionError("Connection failed")
    source = await async_get_media_source(hass)

    with pytest.raises(Unresolvable) as error:
        await source.async_resolve_media(
            MediaSourceItem(
                hass,
                DOMAIN,
                f"{init_integration.entry_id}/unknown",
                None,
            )
        )

    assert error.value.translation_key == "feed_unavailable"


async def test_resolve_invalid_identifier(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
) -> None:
    """Test resolving an invalid media source identifier."""
    source = await async_get_media_source(hass)

    with pytest.raises(Unresolvable) as error:
        await source.async_resolve_media(
            MediaSourceItem(hass, DOMAIN, init_integration.entry_id, None)
        )

    assert error.value.translation_key == "episode_unavailable"
