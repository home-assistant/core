"""Image platform for Habitica integration."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from habiticalib import Avatar, ContentData, extract_avatar

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HABITICA_KEY
from .const import ASSETS_URL
from .coordinator import (
    HabiticaConfigEntry,
    HabiticaDataUpdateCoordinator,
    HabiticaPartyCoordinator,
)
from .entity import HabiticaBase, HabiticaPartyBase, HabiticaPartyMemberBase

PARALLEL_UPDATES = 1


class HabiticaImageEntity(StrEnum):
    """Image entities."""

    AVATAR = "avatar"
    QUEST_IMAGE = "quest_image"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the habitica image platform."""

    coordinator = config_entry.runtime_data
    entities: list[ImageEntity] = [HabiticaImage(hass, coordinator)]

    if party := coordinator.data.user.party.id:
        party_coordinator = hass.data[HABITICA_KEY][party]
        entities.append(
            HabiticaPartyImage(
                hass, party_coordinator, config_entry, coordinator.content
            )
        )
        for subentry_id, subentry in config_entry.subentries.items():
            if (
                subentry.unique_id
                and UUID(subentry.unique_id) in party_coordinator.data.members
            ):
                async_add_entities(
                    [
                        HabiticaPartyMemberImage(
                            hass,
                            coordinator,
                            party_coordinator,
                            subentry,
                        )
                    ],
                    config_subentry_id=subentry_id,
                )

    async_add_entities(entities)


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
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize the image entity."""
        HabiticaBase.__init__(self, coordinator, self.entity_description, subentry)
        ImageEntity.__init__(self, hass)
        self._attr_image_last_updated = dt_util.utcnow()
        if TYPE_CHECKING:
            assert self.user
        self._avatar = extract_avatar(self.user)

    def _handle_coordinator_update(self) -> None:
        """Check if equipped gear and other things have changed since last avatar image generation."""

        if self.user is not None and self._avatar != self.user:
            self._avatar = extract_avatar(self.user)
            self._attr_image_last_updated = dt_util.utcnow()
            self._cache = None

        return super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return cached bytes, otherwise generate new avatar."""
        if not self._cache and self._avatar:
            self._cache = await self.coordinator.generate_avatar(self._avatar)
        return self._cache


class HabiticaPartyMemberImage(HabiticaImage, HabiticaPartyMemberBase):
    """A Habitica party member image entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HabiticaDataUpdateCoordinator,
        party_coordinator: HabiticaPartyCoordinator,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize the image entity."""

        HabiticaPartyMemberBase.__init__(
            self, coordinator, party_coordinator, self.entity_description, subentry
        )
        super().__init__(hass, coordinator, subentry)


class HabiticaPartyImage(HabiticaPartyBase, ImageEntity):
    """A Habitica image entity of a party."""

    entity_description = ImageEntityDescription(
        key=HabiticaImageEntity.QUEST_IMAGE,
        translation_key=HabiticaImageEntity.QUEST_IMAGE,
    )
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HabiticaPartyCoordinator,
        config_entry: HabiticaConfigEntry,
        content: ContentData,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, config_entry, self.entity_description, content)
        ImageEntity.__init__(self, hass)

        self._attr_image_url = self.image_url
        self._attr_image_last_updated = dt_util.utcnow()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if self.image_url != self._attr_image_url:
            self._attr_image_url = self.image_url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()

    @property
    def image_url(self) -> str | None:
        """Return URL of image."""
        return (
            f"{ASSETS_URL}quest_{key}.png"
            if (key := self.coordinator.data.party.quest.key)
            else None
        )

    async def _async_load_image_from_url(self, url: str) -> Image | None:
        """Load an image by url.

        AWS sometimes returns 'application/octet-stream' as content-type
        """
        if response := await self._fetch_url(url):
            return Image(
                content=response.content,
                content_type=self._attr_content_type,
            )
        return None
