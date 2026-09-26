"""Support for INDI Allsky image entities."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aioindiallsky import IndiAllSkyError, MediaData

from homeassistant.components.image import (
    ImageEntity,
    ImageEntityDescription,
    infer_image_type,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import (
    IndiAllSkyConfigEntry,
    IndiAllSkyData,
    IndiAllSkyDataUpdateCoordinator,
)
from .entity import IndiAllSkyEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndiAllSkyImageEntityDescription(ImageEntityDescription):
    """Class describing INDI Allsky image entities."""

    media_fn: Callable[[IndiAllSkyData], MediaData | None]
    fallback_filename: str


IMAGE_DESCRIPTIONS: tuple[IndiAllSkyImageEntityDescription, ...] = (
    IndiAllSkyImageEntityDescription(
        key="latest_keogram",
        translation_key="latest_keogram",
        media_fn=lambda data: data.latest_keogram,
        fallback_filename="latestkeogram",
    ),
    IndiAllSkyImageEntityDescription(
        key="latest_startrail",
        translation_key="latest_startrail",
        media_fn=lambda data: data.latest_startrail,
        fallback_filename="lateststartrail",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndiAllSkyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up INDI Allsky image entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        IndiAllSkyImageEntity(hass, coordinator, entry, description)
        for description in IMAGE_DESCRIPTIONS
    )


class IndiAllSkyImageEntity(IndiAllSkyEntity, ImageEntity):
    """Representation of an INDI Allsky image entity."""

    entity_description: IndiAllSkyImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
        description: IndiAllSkyImageEntityDescription,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, entry)
        ImageEntity.__init__(self, hass)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._last_fetched: datetime | None = None

    @property
    @override
    def image_last_updated(self) -> datetime | None:
        """Return the timestamp when the image was last updated."""
        media = self.entity_description.media_fn(self.coordinator.data)
        if media and media.day_date:
            if dt := dt_util.parse_datetime(media.day_date):
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=dt_util.UTC)
                return dt_util.as_utc(dt)
        return self._last_fetched

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of the image."""
        media = self.entity_description.media_fn(self.coordinator.data)
        filename = (
            media.filename
            if (media and media.filename)
            else self.entity_description.fallback_filename
        )
        try:
            image_bytes = await self.coordinator.client.fetch_image(filename)
        except IndiAllSkyError:
            return None
        else:
            if content_type := infer_image_type(image_bytes):
                self._attr_content_type = content_type
            self._last_fetched = dt_util.utcnow()
            return image_bytes
