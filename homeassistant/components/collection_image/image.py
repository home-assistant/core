"""Support for Collection Image image."""

from __future__ import annotations

import logging
from pathlib import Path
import random

from homeassistant.components.image import ImageEntity
from homeassistant.components.media_player import (
    BrowseError,
    MediaClass,
    async_process_play_media_url,
)
from homeassistant.components.media_source import (
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Collection Image image entities."""
    if media := entry.data.get("media"):
        async_add_entities(
            [
                CollectionImageImageEntity(
                    name=entry.title,
                    media_content_id=media.get("media_content_id"),
                    unique_id=entry.entry_id,
                    hass=hass,
                )
            ]
        )


class CollectionImageImageEntity(ImageEntity):
    """Implement the image entity for Collection Image."""

    _unavailable_logged: bool = False

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

        def set_unavailable() -> None:
            self._unavailable_logged = True
            self._attr_available = False
            self.path = None
            self._attr_image_url = UNDEFINED
            self._async_write_ha_state()

        try:
            media = await async_browse_media(self.hass, self.media_content_id)
        except BrowseError as err:
            if not self._unavailable_logged:
                _LOGGER.info("%s: %s", self.entity_id, str(err))
            set_unavailable()
            return

        if media.children and (
            filtered := [
                item for item in media.children if item.media_class == MediaClass.IMAGE
            ]
        ):
            child = random.choice(filtered)
            try:
                resolved = await async_resolve_media(
                    self.hass, child.media_content_id, self.entity_id
                )
            except Unresolvable as err:
                if not self._unavailable_logged:
                    _LOGGER.info("%s: %s", self.entity_id, str(err))
                set_unavailable()
                return

            self.path = resolved.path
            if resolved.url:
                self._attr_image_url = async_process_play_media_url(
                    self.hass, resolved.url
                )
            else:
                self._attr_image_url = UNDEFINED
            self._attr_content_type = resolved.mime_type
            self._attr_available = True
            self._attr_image_last_updated = dt_util.utcnow()
            if self._unavailable_logged:
                _LOGGER.info(
                    "%s: Has become available again",
                    self.entity_id,
                )
            self._unavailable_logged = False
            self.async_write_ha_state()
            return

        if not self._unavailable_logged:
            _LOGGER.info(
                "%s: No valid images in %s",
                self.entity_id,
                self.media_content_id,
            )
        set_unavailable()
        return

    async def async_added_to_hass(self) -> None:
        """Initialize the first image after entity has been created."""

        async def get_next_image_on_start(_event=None) -> None:
            await self.get_next_image()

        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, get_next_image_on_start
            )
        else:
            await get_next_image_on_start()

    def image(self) -> bytes | None:
        """Return bytes of image."""
        if self.path:
            return self.path.read_bytes()

        return None
