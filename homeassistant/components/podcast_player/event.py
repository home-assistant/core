"""Event entities for Podcast Player."""

from typing import override

from aiopodcast import PodcastEpisode

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_NEW_EPISODE
from .coordinator import PodcastConfigEntry, PodcastUpdateCoordinator
from .helpers import episode_identifier

ATTR_DURATION_SECONDS = "duration_seconds"
ATTR_EPISODE_ID = "episode_id"
ATTR_MEDIA_CONTENT_ID = "media_content_id"
ATTR_PUBLISHED = "published"
ATTR_TITLE = "title"

PARALLEL_UPDATES = 0

ENTITY_DESCRIPTION = EventEntityDescription(
    key="latest_episode",
    translation_key="latest_episode",
    event_types=[EVENT_NEW_EPISODE],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PodcastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the podcast episode event entity."""
    async_add_entities([PodcastEpisodeEvent(entry.runtime_data)])


class PodcastEpisodeEvent(CoordinatorEntity[PodcastUpdateCoordinator], EventEntity):
    """Represent newly discovered podcast episodes."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: PodcastUpdateCoordinator) -> None:
        """Initialize the podcast episode event entity."""
        super().__init__(coordinator)
        self.entity_description = ENTITY_DESCRIPTION
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{ENTITY_DESCRIPTION.key}"
        podcast = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=podcast.title,
            manufacturer=podcast.author,
            configuration_url=podcast.website_url,
            entry_type=DeviceEntryType.SERVICE,
        )

    def _episode_attributes(self, episode: PodcastEpisode) -> dict[str, str | int]:
        """Return compact attributes for a podcast episode event."""
        episode_id = episode_identifier(episode)
        attributes: dict[str, str | int] = {
            ATTR_EPISODE_ID: episode_id,
            ATTR_MEDIA_CONTENT_ID: (
                f"media-source://{DOMAIN}/{self.coordinator.entry.entry_id}/{episode_id}"
            ),
            ATTR_TITLE: episode.title,
        }
        if episode.published is not None:
            attributes[ATTR_PUBLISHED] = episode.published.isoformat()
        if episode.duration_seconds is not None:
            attributes[ATTR_DURATION_SECONDS] = episode.duration_seconds
        return attributes

    @callback
    def _async_handle_latest_episode(self) -> None:
        """Trigger an event when the latest episode changes."""
        if not self.coordinator.data.episodes:
            return

        episode = self.coordinator.data.episodes[0]
        attributes = self._episode_attributes(episode)
        if self.state_attributes.get(ATTR_EPISODE_ID) == attributes[ATTR_EPISODE_ID]:
            return

        self._trigger_event(EVENT_NEW_EPISODE, attributes)
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Handle the entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self._async_handle_latest_episode()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated podcast feed data."""
        self._async_handle_latest_episode()
        super()._handle_coordinator_update()
