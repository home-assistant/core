"""Media player entity for the PlayStation Network Integration."""

from enum import StrEnum
import logging

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PlaystationNetworkConfigEntry, PlaystationNetworkCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_MAP = {"PS5": "PlayStation 5", "PS4": "PlayStation 4"}
PARALLEL_UPDATES = 0


class PlatformType(StrEnum):
    """PlayStation Platform Enum."""

    PS5 = "PS5"
    PS4 = "PS4"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Media Player Entity Setup."""
    coordinator = config_entry.runtime_data

    @callback
    def add_entities() -> None:
        if coordinator.data.platform is None:
            username = coordinator.data.username
            _LOGGER.warning(
                "No console found associated with account: %s. -- Pending creation when available",
                username,
            )
            return

        async_add_entities(
            MediaPlayer(coordinator, platform)
            for platform in coordinator.data.registered_platforms
        )

    coordinator.async_add_listener(add_entities)
    add_entities()


class MediaPlayer(CoordinatorEntity[PlaystationNetworkCoordinator], MediaPlayerEntity):
    """Media player entity representing currently playing game."""

    _attr_media_image_remotely_accessible = True
    _attr_media_content_type = MediaType.GAME

    def __init__(
        self, coordinator: PlaystationNetworkCoordinator, platform: str
    ) -> None:
        """Initialize PSN MediaPlayer."""
        super().__init__(coordinator)
        self._attr_translation_key = "playstation"
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        self._attr_name = None
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{platform}"
        self.key = platform
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=PLATFORM_MAP[self.key],
            manufacturer="Sony Interactive Entertainment",
            model=PLATFORM_MAP[self.key],
        )

    @property
    def state(self) -> MediaPlayerState:
        """Media Player state getter."""
        if (
            self.key == self.coordinator.data.platform.get("platform", "")
            and self.coordinator.data.platform.get("onlineStatus", "") == "online"
        ):
            if (
                self.coordinator.data.available
                and self.coordinator.data.title_metadata.get("npTitleId") is not None
            ):
                return MediaPlayerState.PLAYING
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        """Media title getter."""
        if self.coordinator.data.title_metadata.get(
            "npTitleId"
        ) and self.key == self.coordinator.data.platform.get("platform", ""):
            return self.coordinator.data.title_metadata.get("titleName")
        return None

    @property
    def media_image_url(self) -> str | None:
        """Media image url getter."""
        if self.coordinator.data.title_metadata.get(
            "npTitleId"
        ) and self.key == self.coordinator.data.platform.get("platform", ""):
            title = self.coordinator.data.title_metadata
            if title.get("format", "") == PlatformType.PS5:
                return title.get("conceptIconUrl")

            if title.get("format", "") == PlatformType.PS4:
                return title.get("npTitleIconUrl")
        return None

    @property
    def is_on(self) -> bool:
        """Is user available on the Playstation Network."""
        return (
            self.coordinator.data.available is True
            and self.key == self.coordinator.data.platform.get("platform", "")
        )
