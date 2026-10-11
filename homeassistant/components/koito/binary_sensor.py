"""Expose Koito's normalized now-playing cache flag."""

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import KoitoEntity
from .models import MusicItem

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import KoitoConfigEntry, KoitoCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KoitoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the cached playback flag."""
    async_add_entities([KoitoNowPlayingBinarySensor(entry.runtime_data, entry)])


class KoitoNowPlayingBinarySensor(KoitoEntity, BinarySensorEntity):
    """An endpoint failure is unavailable; a valid inactive flag is off."""

    _attr_translation_key = "now_playing"

    def __init__(self, coordinator: KoitoCoordinator, entry: KoitoConfigEntry) -> None:
        """Initialize the stable flag entity."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_now_playing"

    @property
    @override
    def available(self) -> bool:
        """Keep optional endpoint failures separate from inactive playback."""
        return super().available and self.coordinator.data.now_playing is not None

    @property
    @override
    def is_on(self) -> bool | None:
        """Read the validated playback flag."""
        now_playing = self.coordinator.data.now_playing
        return now_playing.currently_playing if now_playing is not None else None

    @property
    def _track(self) -> MusicItem | None:
        now_playing = self.coordinator.data.now_playing
        return (
            now_playing.track
            if now_playing is not None and now_playing.currently_playing
            else None
        )

    @property
    @override
    def entity_picture(self) -> str | None:
        """Expose active-track artwork already resolved by the typed adapter."""
        track = self._track
        return track.image_url if track is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the normalized active-track details."""
        track = self._track
        if track is None:
            return {}
        attributes: dict[str, Any] = {}
        if track.title is not None:
            attributes["title"] = track.title
        if track.artists:
            attributes["artists"] = list(track.artists)
        if track.album_id is not None:
            attributes["album_id"] = track.album_id
        if track.image_url is not None:
            attributes["image_url"] = track.image_url
        return attributes
