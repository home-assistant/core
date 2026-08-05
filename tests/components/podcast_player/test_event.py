"""Tests for Podcast Player event entities."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aiopodcast import Podcast, PodcastConnectionError, PodcastEpisode

from homeassistant.components.event import EventExtraStoredData
from homeassistant.components.podcast_player.const import (
    DOMAIN,
    EVENT_NEW_EPISODE,
    SCAN_INTERVAL,
)
from homeassistant.components.podcast_player.coordinator import PodcastConfigEntry
from homeassistant.components.podcast_player.event import (
    ATTR_DURATION_SECONDS,
    ATTR_EPISODE_ID,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_PUBLISHED,
    ATTR_TITLE,
)
from homeassistant.components.podcast_player.helpers import episode_identifier
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

ENTITY_ID = "event.example_podcast"


def _new_episode(podcast: Podcast) -> PodcastEpisode:
    """Return a new episode based on the fixture podcast."""
    published = podcast.episodes[0].published
    assert published is not None
    return replace(
        podcast.episodes[0],
        title="Second episode",
        guid="episode-two",
        published=published + timedelta(days=1),
        duration_seconds=2400,
    )


async def test_latest_episode_event(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    podcast: Podcast,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the latest episode event and service device."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    episode = podcast.episodes[0]
    episode_id = episode_identifier(episode)
    assert episode.published is not None
    assert state.attributes["event_type"] == EVENT_NEW_EPISODE
    assert state.attributes[ATTR_TITLE] == episode.title
    assert state.attributes[ATTR_EPISODE_ID] == episode_id
    assert state.attributes[ATTR_PUBLISHED] == episode.published.isoformat()
    assert state.attributes[ATTR_DURATION_SECONDS] == episode.duration_seconds
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == (
        f"media-source://{DOMAIN}/{init_integration.entry_id}/{episode_id}"
    )
    assert episode.enclosure.url not in state.attributes.values()

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{init_integration.entry_id}_latest_episode"

    assert entity_entry.device_id is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.name == podcast.title
    assert device_entry.manufacturer == podcast.author
    assert device_entry.configuration_url == podcast.website_url


async def test_poll_discovers_new_episode(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test polling triggers an event for a new latest episode."""
    old_state = hass.states.get(ENTITY_ID)
    assert old_state is not None
    episode = _new_episode(podcast)
    mock_client.async_fetch.return_value = replace(
        podcast, episodes=(episode, *podcast.episodes)
    )

    async_fire_time_changed(
        hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != old_state.state
    assert state.attributes[ATTR_TITLE] == episode.title
    assert state.attributes[ATTR_EPISODE_ID] == episode_identifier(episode)
    assert mock_client.async_fetch.await_count == 2


async def test_poll_does_not_repeat_latest_episode(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test polling an unchanged feed does not repeat the event."""
    old_state = hass.states.get(ENTITY_ID)
    assert old_state is not None

    async_fire_time_changed(
        hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID) == old_state
    assert mock_client.async_fetch.await_count == 2


async def test_restored_episode_is_not_repeated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test restoring the latest episode prevents a duplicate event."""
    episode = podcast.episodes[0]
    episode_id = episode_identifier(episode)
    assert episode.published is not None
    attributes = {
        ATTR_DURATION_SECONDS: episode.duration_seconds,
        ATTR_EPISODE_ID: episode_id,
        ATTR_MEDIA_CONTENT_ID: (
            f"media-source://{DOMAIN}/{mock_config_entry.entry_id}/{episode_id}"
        ),
        ATTR_PUBLISHED: episode.published.isoformat(),
        ATTR_TITLE: episode.title,
    }
    restored_timestamp = "2026-08-05T10:00:00+00:00"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ENTITY_ID, restored_timestamp),
                EventExtraStoredData(EVENT_NEW_EPISODE, attributes).as_dict(),
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert dt_util.parse_datetime(state.state) == dt_util.parse_datetime(
        restored_timestamp
    )
    assert state.attributes[ATTR_EPISODE_ID] == episode_id
    mock_client.async_fetch.assert_awaited_once()


async def test_event_unavailable_and_recovers(
    hass: HomeAssistant,
    init_integration: PodcastConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test the event entity becomes unavailable and recovers."""
    old_state = hass.states.get(ENTITY_ID)
    assert old_state is not None
    mock_client.async_fetch.side_effect = PodcastConnectionError("Connection failed")

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_client.async_fetch.side_effect = None
    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == old_state.state

    episode = _new_episode(podcast)
    mock_client.async_fetch.return_value = replace(
        podcast, episodes=(episode, *podcast.episodes)
    )

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_EPISODE_ID] == episode_identifier(episode)


async def test_event_without_optional_episode_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test an event for an episode without optional metadata."""
    episode = replace(
        podcast.episodes[0],
        guid=None,
        published=None,
        duration_seconds=None,
    )
    mock_client.async_fetch.return_value = replace(podcast, episodes=(episode,))
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_EPISODE_ID] == episode_identifier(episode)
    assert ATTR_PUBLISHED not in state.attributes
    assert ATTR_DURATION_SECONDS not in state.attributes


async def test_event_with_empty_feed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test setting up an event entity for a feed without episodes."""
    mock_client.async_fetch.return_value = replace(podcast, episodes=())
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
