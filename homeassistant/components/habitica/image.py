"""Image platform for Habitica integration."""

from __future__ import annotations

from dataclasses import asdict
from enum import StrEnum

from habiticalib import UserStyles

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HabiticaConfigEntry
from .coordinator import HabiticaDataUpdateCoordinator
from .entity import HabiticaBase


class HabiticaImageEntity(StrEnum):
    """Image entities."""

    AVATAR = "avatar"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    _current_appearance: UserStyles | None = None
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

    def _handle_coordinator_update(self) -> None:
        """Check if equipped gear and other things have changed since last avatar image generation."""
        new_appearance = UserStyles.from_dict(asdict(self.coordinator.data.user))

        if self._current_appearance != new_appearance:
            self._current_appearance = new_appearance
            self._attr_image_last_updated = dt_util.utcnow()
            self._cache = None

        return super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return cached bytes, otherwise generate new avatar."""
        if not self._cache and self._current_appearance:
            self._cache = await self.coordinator.generate_avatar(
                self._current_appearance
            )
        return self._cache
