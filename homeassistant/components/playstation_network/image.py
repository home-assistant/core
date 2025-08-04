"""Image platform for PlayStation Network."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import (
    PlayStationNetworkBaseCoordinator,
    PlaystationNetworkConfigEntry,
    PlaystationNetworkData,
    PlaystationNetworkFriendDataCoordinator,
    PlaystationNetworkUserDataCoordinator,
)
from .entity import PlaystationNetworkServiceEntity
from .helpers import get_game_title_info

PARALLEL_UPDATES = 0


class PlaystationNetworkImage(StrEnum):
    """PlayStation Network images."""

    AVATAR = "avatar"
    SHARE_PROFILE = "share_profile"
    NOW_PLAYING_IMAGE = "now_playing_image"


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkImageEntityDescription(ImageEntityDescription):
    """Image entity description."""

    image_url_fn: Callable[[PlaystationNetworkData], str | None]


IMAGE_DESCRIPTIONS_ME: tuple[PlaystationNetworkImageEntityDescription, ...] = (
    PlaystationNetworkImageEntityDescription(
        key=PlaystationNetworkImage.SHARE_PROFILE,
        translation_key=PlaystationNetworkImage.SHARE_PROFILE,
        image_url_fn=lambda data: data.shareable_profile_link["shareImageUrl"],
    ),
)
IMAGE_DESCRIPTIONS_ALL: tuple[PlaystationNetworkImageEntityDescription, ...] = (
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
    PlaystationNetworkImageEntityDescription(
        key=PlaystationNetworkImage.NOW_PLAYING_IMAGE,
        translation_key=PlaystationNetworkImage.NOW_PLAYING_IMAGE,
        image_url_fn=(
            lambda data: get_game_title_info(data.presence).get("conceptIconUrl")
            or get_game_title_info(data.presence).get("npTitleIconUrl")
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
            for description in IMAGE_DESCRIPTIONS_ME + IMAGE_DESCRIPTIONS_ALL
        ]
    )

    for (
        subentry_id,
        friend_data_coordinator,
    ) in config_entry.runtime_data.friends.items():
        async_add_entities(
            [
                PlaystationNetworkFriendImageEntity(
                    hass,
                    friend_data_coordinator,
                    description,
                    config_entry.subentries[subentry_id],
                )
                for description in IMAGE_DESCRIPTIONS_ALL
            ],
            config_subentry_id=subentry_id,
        )


class PlaystationNetworkImageBaseEntity(PlaystationNetworkServiceEntity, ImageEntity):
    """An image entity."""

    entity_description: PlaystationNetworkImageEntityDescription
    coordinator: PlayStationNetworkBaseCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PlayStationNetworkBaseCoordinator,
        entity_description: PlaystationNetworkImageEntityDescription,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, entity_description, subentry)
        ImageEntity.__init__(self, hass)

        self._attr_image_url = self.entity_description.image_url_fn(coordinator.data)
        self._attr_image_last_updated = dt_util.utcnow()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if TYPE_CHECKING:
            assert isinstance(self.coordinator.data, PlaystationNetworkData)
        url = self.entity_description.image_url_fn(self.coordinator.data)

        if url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()


class PlaystationNetworkImageEntity(PlaystationNetworkImageBaseEntity):
    """An image entity."""

    coordinator: PlaystationNetworkUserDataCoordinator


class PlaystationNetworkFriendImageEntity(PlaystationNetworkImageBaseEntity):
    """An image entity."""

    coordinator: PlaystationNetworkFriendDataCoordinator
