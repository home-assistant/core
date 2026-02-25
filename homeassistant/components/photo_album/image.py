"""Support for Photo Album image."""

from __future__ import annotations

import logging
from pathlib import Path
import random

from homeassistant.components.image import ImageEntity
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Photo Album image entities."""
    if media := entry.data.get("media"):
        async_add_entities(
            [
                PhotoAlbumImageEntity(
                    name=entry.title,
                    media_content_id=media.get("media_content_id"),
                    unique_id=entry.entry_id,
                    hass=hass,
                )
            ]
        )


class PhotoAlbumImageEntity(ImageEntity):
    """Implement the image entity for Photo Album."""

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

    async def get_next_image(self) -> None:
        """Update the image entity with the next image from the source media."""

        path: Path | None = None
        content_type: str = ""
        try:
            media = await async_browse_media(self.hass, self.media_content_id)
        except BrowseError as err:
            _LOGGER.error("%s: %s", self.entity_id, str(err))
        else:
            if media.children and (
                filtered := [
                    item
                    for item in media.children
                    if item.media_class == MediaClass.IMAGE
                ]
            ):
                child = random.choice(filtered)
                try:
                    resolved = await async_resolve_media(
                        self.hass, child.media_content_id, self.entity_id
                    )
                except Unresolvable as err:
                    _LOGGER.error("%s: %s", self.entity_id, str(err))
                else:
                    path = resolved.path
                    content_type = resolved.mime_type
            else:
                _LOGGER.warning(
                    "%s: No valid images in %s",
                    self.entity_id,
                    self.media_content_id,
                )

        self.path = path
        self._attr_content_type = content_type
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Initialize the first image after entity has been created."""

        async def get_next_image_on_start(_event=None) -> None:
            await self.get_next_image()

        if self.hass.state != CoreState.running:
            remove_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, get_next_image_on_start
            )
            self.async_on_remove(remove_listener)
        else:
            await get_next_image_on_start()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if self.path:
            return await self.hass.async_add_executor_job(self.path.read_bytes)

        return None
