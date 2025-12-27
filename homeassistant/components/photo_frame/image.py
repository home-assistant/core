"""Support for Photo Frame image."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import random

from homeassistant.components.image import ImageEntity, ImageEntityDescription
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


@dataclass(frozen=True, kw_only=True)
class PhotoFrameImageEntityDescription(ImageEntityDescription):
    """Photo Frame image entity description."""

    media_content_id: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Photo Frame image entities."""
    if media := entry.data.get("media"):
        description = PhotoFrameImageEntityDescription(
            key="image",
            name=entry.title,
            media_content_id=media.get("media_content_id"),
        )
        async_add_entities(
            [
                PhotoFrameImageEntity(
                    description,
                    unique_id=entry.entry_id,
                    hass=hass,
                )
            ]
        )


class PhotoFrameImageEntity(ImageEntity):
    """Implement the image entity for Photo Frame."""

    entity_description: PhotoFrameImageEntityDescription
    path: Path | None

    def __init__(
        self,
        description: PhotoFrameImageEntityDescription,
        unique_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass)
        self.entity_description = description
        self.path = None
        self._attr_unique_id = unique_id
        self._attr_name = (
            description.name if isinstance(description.name, str) else None
        )

    async def get_next_image(self) -> None:
        """Update the image entity with the next image from the source media."""
        try:
            media = await async_browse_media(
                self.hass, self.entity_description.media_content_id
            )
            if media.children:
                filtered = [
                    item
                    for item in media.children
                    if item.media_class == MediaClass.IMAGE
                ]
                if filtered:
                    child = random.choice(filtered)
                    resolved = await async_resolve_media(
                        self.hass, child.media_content_id, self.entity_id
                    )
                    self.path = resolved.path
                    self._attr_content_type = resolved.mime_type
                    self._attr_image_last_updated = dt_util.utcnow()
                    self.async_write_ha_state()
                    return

            _LOGGER.warning(
                "%s: No valid images in %s",
                self.entity_id,
                self.entity_description.media_content_id,
            )
        except (BrowseError, Unresolvable) as err:
            _LOGGER.error("%s: %s", self.entity_id, str(err))

        self.path = None
        self._attr_content_type = ""
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Initialize the first image after entity has been created."""

        async def get_next_image_on_start(_event) -> None:
            await self.get_next_image()

        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, get_next_image_on_start
            )
        else:
            await self.get_next_image()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if self.path:
            return await self.hass.async_add_executor_job(self.path.read_bytes)

        return None
