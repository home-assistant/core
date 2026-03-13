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

from .const import SUBENTRY_TYPE_FRIEND, SUBENTRY_TYPE_GAME
from .coordinator import (
    XboxConfigEntry,
    XboxPresenceCoordinator,
    XboxTitleHistoryCoordinator,
)
from .entity import (
    XboxBaseEntity,
    XboxBaseEntityDescription,
    XboxGameBaseEntity,
    profile_pic,
    to_https,
)

PARALLEL_UPDATES = 0


class XboxImage(StrEnum):
    """Xbox image."""

    NOW_PLAYING = "now_playing"
    GAMERPIC = "gamerpic"
    AVATAR = "avatar"
    TITLE_IMAGE = "title_image"


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
            lambda person, _: (
                f"https://avatar-ssl.xboxlive.com/avatar/{person.gamertag}/avatar-body.png"
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox images."""
    coordinator = config_entry.runtime_data.presence
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
                and subentry.subentry_type == SUBENTRY_TYPE_FRIEND
            ],
            config_subentry_id=subentry_id,
        )

    title_history = config_entry.runtime_data.title_history
    for subentry_id, subentry in config_entry.subentries.items():
        if (
            subentry.unique_id
            and subentry.unique_id in title_history.data
            and subentry.subentry_type == SUBENTRY_TYPE_GAME
        ):
            async_add_entities(
                [XboxGameTitleImageEntity(hass, title_history, subentry.unique_id)],
                config_subentry_id=subentry_id,
            )


class XboxImageEntity(XboxBaseEntity, ImageEntity):
    """An image entity."""

    entity_description: XboxImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: XboxPresenceCoordinator,
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


class XboxGameTitleImageEntity(XboxGameBaseEntity, ImageEntity):
    """An image entity."""

    entity_description = ImageEntityDescription(
        key=XboxImage.TITLE_IMAGE,
        translation_key=XboxImage.TITLE_IMAGE,
        name=None,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: XboxTitleHistoryCoordinator,
        title_id: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, title_id, self.entity_description)
        ImageEntity.__init__(self, hass)

        self._attr_image_url = to_https(self.data.display_image)
        self._attr_image_last_updated = dt_util.utcnow()
