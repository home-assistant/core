"""Image platform for the Xbox integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, override

from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.titlehub.models import Title

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import XboxConfigEntry, XboxPresenceCoordinator
from .entity import XboxBaseEntity, XboxBaseEntityDescription, profile_pic

PARALLEL_UPDATES = 0


class XboxImage(StrEnum):
    """Xbox image."""

    NOW_PLAYING = "now_playing"
    GAMERPIC = "gamerpic"
    AVATAR = "avatar"
    POSTER = "poster"
    BRANDED_KEY_ART = "branded_key_art"
    TITLED_HERO_ART = "titled_hero_art"
    SUPER_HERO_ART = "super_hero_art"
    BOX_ART = "box_art"
    FEATURE_PROMOTIONAL_SQUARE_ART = "feature_promotional_square_art"


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
        key=XboxImage.POSTER,
        translation_key=XboxImage.POSTER,
        image_url_fn=lambda _, title: (
            next((img.url for img in title.images if img.type == "Poster"), None)
            if title and title.images
            else None
        ),
    ),
    XboxImageEntityDescription(
        key=XboxImage.BRANDED_KEY_ART,
        translation_key=XboxImage.BRANDED_KEY_ART,
        image_url_fn=lambda _, title: (
            next((img.url for img in title.images if img.type == "BrandedKeyArt"), None)
            if title and title.images
            else None
        ),
    ),
    XboxImageEntityDescription(
        key=XboxImage.TITLED_HERO_ART,
        translation_key=XboxImage.TITLED_HERO_ART,
        image_url_fn=lambda _, title: (
            next((img.url for img in title.images if img.type == "TitledHeroArt"), None)
            if title and title.images
            else None
        ),
    ),
    XboxImageEntityDescription(
        key=XboxImage.SUPER_HERO_ART,
        translation_key=XboxImage.SUPER_HERO_ART,
        image_url_fn=lambda _, title: (
            next((img.url for img in title.images if img.type == "SuperHeroArt"), None)
            if title and title.images
            else None
        ),
    ),
    XboxImageEntityDescription(
        key=XboxImage.BOX_ART,
        translation_key=XboxImage.BOX_ART,
        image_url_fn=lambda _, title: (
            next((img.url for img in title.images if img.type == "BoxArt"), None)
            if title and title.images
            else None
        ),
    ),
    XboxImageEntityDescription(
        key=XboxImage.FEATURE_PROMOTIONAL_SQUARE_ART,
        translation_key=XboxImage.FEATURE_PROMOTIONAL_SQUARE_ART,
        image_url_fn=lambda _, title: (
            next(
                (
                    img.url
                    for img in title.images
                    if img.type == "FeaturePromotionalSquareArt"
                ),
                None,
            )
            if title and title.images
            else None
        ),
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

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if self.available:
            url = self.entity_description.image_url_fn(self.data, self.title_info)

            if url != self._attr_image_url:
                self._attr_image_url = url
                self._cached_image = None
                self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()
