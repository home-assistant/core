"""Image platform for the Steam integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, override

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import STEAM_API_URL, STEAM_ICON_URL, SUBENTRY_TYPE_FRIEND
from .coordinator import PlayerData, SteamConfigEntry, SteamDataUpdateCoordinator
from .entity import SteamEntity

PARALLEL_UPDATES = 0


class SteamImage(StrEnum):
    """Steam images."""

    AVATAR = "avatar"
    MAIN_CAPSULE = "main_capsule"
    HEADER_CAPSULE = "header_capsule"
    SMALL_CAPSULE = "small_capsule"
    VERTICAL_CAPSULE = "vertical_capsule"
    LIBRARY_CAPSULE = "library_capsule"
    LIBRARY_HERO = "library_hero"
    LIBRARY_LOGO = "library_logo"
    PAGE_BACKGROUND = "page_background"
    APP_ICON = "app_icon"


@dataclass(kw_only=True, frozen=True)
class SteamImageEntityDescription(ImageEntityDescription):
    """Steam image description."""

    image_url_fn: Callable[[PlayerData, dict[str, str]], str | None]
    available_fn: Callable[[PlayerData], bool] = lambda x: x.gameid is not None


IMAGE_DESCRIPTIONS: tuple[SteamImageEntityDescription, ...] = (
    SteamImageEntityDescription(
        key=SteamImage.AVATAR,
        translation_key=SteamImage.AVATAR,
        image_url_fn=lambda x, _: x.avatarfull,
        entity_registry_enabled_default=False,
        available_fn=lambda _: True,
    ),
    SteamImageEntityDescription(
        key=SteamImage.MAIN_CAPSULE,
        translation_key=SteamImage.MAIN_CAPSULE,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/capsule_616x353.jpg" if x.gameid else None
        ),
    ),
    SteamImageEntityDescription(
        key=SteamImage.HEADER_CAPSULE,
        translation_key=SteamImage.HEADER_CAPSULE,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/header.jpg" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.APP_ICON,
        translation_key=SteamImage.APP_ICON,
        image_url_fn=lambda x, icons: (
            f"{STEAM_ICON_URL}{x.gameid}/{i}.jpg"
            if x.gameid and (i := icons.get(x.gameid))
            else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.SMALL_CAPSULE,
        translation_key=SteamImage.SMALL_CAPSULE,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/capsule_231x87.jpg" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.LIBRARY_CAPSULE,
        translation_key=SteamImage.LIBRARY_CAPSULE,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/library_600x900_2x.jpg" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.LIBRARY_HERO,
        translation_key=SteamImage.LIBRARY_HERO,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/library_hero.jpg" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.LIBRARY_LOGO,
        translation_key=SteamImage.LIBRARY_LOGO,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/logo.png" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.PAGE_BACKGROUND,
        translation_key=SteamImage.PAGE_BACKGROUND,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/page_bg_generated_v6b.jpg" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
    SteamImageEntityDescription(
        key=SteamImage.VERTICAL_CAPSULE,
        translation_key=SteamImage.VERTICAL_CAPSULE,
        image_url_fn=lambda x, _: (
            f"{STEAM_API_URL}{x.gameid}/hero_capsule.jpg" if x.gameid else None
        ),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Steam platform."""
    coordinator = entry.runtime_data
    if TYPE_CHECKING:
        assert entry.unique_id

    async_add_entities(
        SteamImageEntity(hass, coordinator, entry.unique_id, description)
        for description in IMAGE_DESCRIPTIONS
        if entry.unique_id in coordinator.data
    )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_FRIEND):
        async_add_entities(
            [
                SteamImageEntity(hass, coordinator, subentry.unique_id, description)
                for description in IMAGE_DESCRIPTIONS
                if subentry.unique_id in coordinator.data
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SteamImageEntity(SteamEntity, ImageEntity):
    """An image entity."""

    entity_description: SteamImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SteamDataUpdateCoordinator,
        steamid: str,
        entity_description: SteamImageEntityDescription,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, steamid, entity_description)
        ImageEntity.__init__(self, hass)

        self._attr_image_url = self.entity_description.image_url_fn(
            self.coordinator.data[self._steamid], self.coordinator.game_icons
        )
        self._attr_image_last_updated = dt_util.utcnow()

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        url = self.entity_description.image_url_fn(
            self.coordinator.data[self._steamid], self.coordinator.game_icons
        )

        if url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data[self._steamid]
        )
