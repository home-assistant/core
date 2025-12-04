"""Image platform for the Xbox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.titlehub.models import Title

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import XboxConfigEntry, XboxUpdateCoordinator
from .entity import XboxBaseEntity, XboxBaseEntityDescription, profile_pic

PARALLEL_UPDATES = 0


class XboxImage(StrEnum):
    """Xbox image."""

    NOW_PLAYING = "now_playing"
    GAMERPIC = "gamerpic"
    AVATAR = "avatar"


@dataclass(kw_only=True, frozen=True)
class XboxImageEntityDescription(XboxBaseEntityDescription, ImageEntityDescription):
    """Xbox image description."""

    image_url_fn: Callable[[Person, Title | None], str | None]


IMAGE_DESCRIPTIONS: tuple[XboxImageEntityDescription, ...] = (
    XboxImageEntityDescription(
        key=XboxImage.GAMERPIC,
        translation_key=XboxImage.GAMERPIC,
        image_url_fn=profile_pic,
    ),
    XboxImageEntityDescription(
        key=XboxImage.NOW_PLAYING,
        translation_key=XboxImage.NOW_PLAYING,
        image_url_fn=lambda _, title: title.display_image if title else None,
    ),
    XboxImageEntityDescription(
        key=XboxImage.AVATAR,
        translation_key=XboxImage.AVATAR,
        image_url_fn=(
            lambda person,
            _: f"https://avatar-ssl.xboxlive.com/avatar/{person.gamertag}/avatar-body.png"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox images."""
    coordinator = config_entry.runtime_data.status
    if TYPE_CHECKING:
        assert config_entry.unique_id
    async_add_entities(
        [
            XboxImageEntity(hass, coordinator, config_entry.unique_id, description)
            for description in IMAGE_DESCRIPTIONS
        ]
    )

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [
                XboxImageEntity(hass, coordinator, subentry.unique_id, description)
                for description in IMAGE_DESCRIPTIONS
                if subentry.unique_id
                and subentry.unique_id in coordinator.data.presence
                and subentry.subentry_type == "friend"
            ],
            config_subentry_id=subentry_id,
        )


class XboxImageEntity(XboxBaseEntity, ImageEntity):
    """An image entity."""

    entity_description: XboxImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: XboxUpdateCoordinator,
        xuid: str,
        entity_description: XboxImageEntityDescription,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, xuid, entity_description)
        ImageEntity.__init__(self, hass)

        self._attr_image_url = self.entity_description.image_url_fn(
            self.data, self.title_info
        )
        self._attr_image_last_updated = dt_util.utcnow()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if self.available:
            url = self.entity_description.image_url_fn(self.data, self.title_info)

            if url != self._attr_image_url:
                self._attr_image_url = url
                self._cached_image = None
                self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()
