"""Support for Collection Image image."""

import logging
from pathlib import Path
import random
from typing import override

from homeassistant.components.image import DEFAULT_CONTENT_TYPE, ImageEntity
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    async_process_play_media_url,
)
from homeassistant.components.media_source import (
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util import dt as dt_util

from .const import CONF_MEDIA, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Collection Image image entities."""
    media = entry.data[CONF_MEDIA]
    async_add_entities(
        [
            CollectionImageImageEntity(
                name=entry.title,
                media_content_id=media["media_content_id"],
                unique_id=entry.entry_id,
                hass=hass,
            )
        ]
    )


class CollectionImageImageEntity(ImageEntity):
    """Implement the image entity for Collection Image."""

    path: Path | None

    def __init__(
        self,
        name: str,
        media_content_id: str,
        unique_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass)
        self.path = None
        self._attr_unique_id = unique_id
        self._attr_name = name
        self.media_content_id = media_content_id

    def set_unavailable(self) -> None:
        """Set the entity to unavailable state."""
        self._attr_available = False
        self.path = None
        self._attr_image_url = UNDEFINED
        self._cached_image = None
        self.async_write_ha_state()

    async def get_valid_images(self) -> list[BrowseMedia]:
        """Given the configured media directory for the entity, get a list of all child images."""
        try:
            media = await async_browse_media(self.hass, self.media_content_id)
        except BrowseError as err:
            _LOGGER.warning("%s: %s", self.entity_id, str(err))
            return []

        images = [
            item
            for item in (media.children or [])
            if item.media_class == MediaClass.IMAGE
        ]
        if not images:
            _LOGGER.warning(
                "%s: No valid images in %s",
                self.entity_id,
                self.media_content_id,
            )
        return images

    async def get_random_image(self) -> None:
        """Update the image entity with a random image from the source media."""

        filtered = await self.get_valid_images()
        if not filtered:
            self.set_unavailable()
            return

        child = random.choice(filtered)
        self._attr_available = True
        await self.update_image(child.media_content_id)

    async def update_image(self, image_id: str) -> None:
        """Update the entity from the image_id."""
        self._cached_image = None
        try:
            resolved = await async_resolve_media(self.hass, image_id, self.entity_id)
        except Unresolvable as err:
            _LOGGER.warning("%s: %s", self.entity_id, str(err))
            self._attr_image_last_updated = None
            self.path = None
            self._attr_image_url = UNDEFINED
            self._attr_content_type = DEFAULT_CONTENT_TYPE
            self.async_write_ha_state()
            return

        if resolved.url:
            self.path = None
            self._attr_image_url = async_process_play_media_url(self.hass, resolved.url)
        else:
            self.path = resolved.path
            self._attr_image_url = UNDEFINED

        self._attr_content_type = resolved.mime_type
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Initialize the first image after entity has been created."""

        async def get_random_image_on_start(_hass: HomeAssistant) -> None:
            await self.get_random_image()

        self.async_on_remove(async_at_started(self.hass, get_random_image_on_start))

    @override
    def image(self) -> bytes | None:
        """Return bytes of image."""
        if self.path:
            try:
                return self.path.read_bytes()
            except OSError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="image_read_error",
                    translation_placeholders={
                        "path": str(self.path),
                        "error": str(err),
                    },
                ) from err

        return None
