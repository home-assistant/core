"""Image platform for PlayStation Network."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import (
    PlaystationNetworkConfigEntry,
    PlaystationNetworkData,
    PlaystationNetworkUserDataCoordinator,
)
from .entity import PlaystationNetworkServiceEntity

PARALLEL_UPDATES = 0


class PlaystationNetworkImage(StrEnum):
    """PlayStation Network images."""

    AVATAR = "avatar"
    SHARE_PROFILE = "share_profile"


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkImageEntityDescription(ImageEntityDescription):
    """Image entity description."""

    image_url_fn: Callable[[PlaystationNetworkData], str | None]


IMAGE_DESCRIPTIONS: tuple[PlaystationNetworkImageEntityDescription, ...] = (
    PlaystationNetworkImageEntityDescription(
        key=PlaystationNetworkImage.SHARE_PROFILE,
        translation_key=PlaystationNetworkImage.SHARE_PROFILE,
        image_url_fn=lambda data: data.shareable_profile_link["shareImageUrl"],
    ),
    PlaystationNetworkImageEntityDescription(
        key=PlaystationNetworkImage.AVATAR,
        translation_key=PlaystationNetworkImage.AVATAR,
        image_url_fn=(
            lambda data: next(
                (
                    pic.get("url")
                    for pic in data.profile["avatars"]
                    if pic.get("size") == "xl"
                ),
                None,
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up image platform."""

    coordinator = config_entry.runtime_data.user_data

    async_add_entities(
        [
            PlaystationNetworkImageEntity(hass, coordinator, description)
            for description in IMAGE_DESCRIPTIONS
        ]
    )


class PlaystationNetworkImageEntity(PlaystationNetworkServiceEntity, ImageEntity):
    """An image entity."""

    entity_description: PlaystationNetworkImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PlaystationNetworkUserDataCoordinator,
        entity_description: PlaystationNetworkImageEntityDescription,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, entity_description)
        ImageEntity.__init__(self, hass)

        self._attr_image_url = self.entity_description.image_url_fn(coordinator.data)
        self._attr_image_last_updated = dt_util.utcnow()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        url = self.entity_description.image_url_fn(self.coordinator.data)

        if url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()
