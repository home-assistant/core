"""Image platform for Habitica integration."""

from __future__ import annotations

from enum import StrEnum

from habiticalib import Avatar, extract_avatar

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import HabiticaConfigEntry, HabiticaDataUpdateCoordinator
from .entity import HabiticaBase

PARALLEL_UPDATES = 1


class HabiticaImageEntity(StrEnum):
    """Image entities."""

    AVATAR = "avatar"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the habitica image platform."""

    coordinator = config_entry.runtime_data

    async_add_entities([HabiticaImage(hass, coordinator)])


class HabiticaImage(HabiticaBase, ImageEntity):
    """A Habitica image entity."""

    entity_description = ImageEntityDescription(
        key=HabiticaImageEntity.AVATAR,
        translation_key=HabiticaImageEntity.AVATAR,
    )
    _attr_content_type = "image/png"
    _avatar: Avatar | None = None
    _cache: bytes | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HabiticaDataUpdateCoordinator,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, self.entity_description)
        ImageEntity.__init__(self, hass)
        self._attr_image_last_updated = dt_util.utcnow()
        self._avatar = extract_avatar(self.coordinator.data.user)

    def _handle_coordinator_update(self) -> None:
        """Check if equipped gear and other things have changed since last avatar image generation."""

        if self._avatar != self.coordinator.data.user:
            self._avatar = extract_avatar(self.coordinator.data.user)
            self._attr_image_last_updated = dt_util.utcnow()
            self._cache = None

        return super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return cached bytes, otherwise generate new avatar."""
        if not self._cache and self._avatar:
            self._cache = await self.coordinator.generate_avatar(self._avatar)
        return self._cache
