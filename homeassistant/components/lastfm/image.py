"""Image platform for the Last.fm integration."""

from typing import override

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_USERS
from .coordinator import LastFMConfigEntry, LastFMDataUpdateCoordinator
from .entity import LastFmEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LastFMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Last.fm image entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        LastFmNowPlayingImage(hass, coordinator, username, entry.entry_id)
        for username in entry.options[CONF_USERS]
    )


class LastFmNowPlayingImage(LastFmEntity, ImageEntity):
    """Album art of the track a Last.fm user is playing."""

    _attr_translation_key = "now_playing"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, username, entry_id)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{self._user_hash}_now_playing"
        self._attr_image_url = self._now_playing_image()
        self._attr_image_last_updated = dt_util.utcnow()

    def _now_playing_image(self) -> str | None:
        """Return the album art of the playing track."""
        if self.user_data is None:
            return None
        return self.user_data.now_playing_image

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update the image when the album art changes."""
        if (url := self._now_playing_image()) != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
