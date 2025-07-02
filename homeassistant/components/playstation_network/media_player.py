"""Media player entity for the PlayStation Network Integration."""

import logging
from typing import TYPE_CHECKING

from psnawp_api.models.trophies import PlatformType

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PlaystationNetworkConfigEntry, PlaystationNetworkCoordinator
from .const import DOMAIN, SUPPORTED_PLATFORMS

_LOGGER = logging.getLogger(__name__)


PLATFORM_MAP = {
    PlatformType.PS5: "PlayStation 5",
    PlatformType.PS4: "PlayStation 4",
    PlatformType.PS3: "PlayStation 3",
    PlatformType.PSPC: "PlayStation PC",
}
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Media Player Entity Setup."""
    coordinator = config_entry.runtime_data
    devices_added: set[PlatformType] = set()
    device_reg = dr.async_get(hass)
    entities = []

    @callback
    def add_entities() -> None:
        nonlocal devices_added

        if not SUPPORTED_PLATFORMS - devices_added:
            remove_listener()

        new_platforms = set(coordinator.data.active_sessions.keys()) - devices_added
        if new_platforms:
            async_add_entities(
                PsnMediaPlayerEntity(coordinator, platform_type)
                for platform_type in new_platforms
            )
            devices_added |= new_platforms

    for platform in SUPPORTED_PLATFORMS:
        if device_reg.async_get_device(
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.unique_id}_{platform.value}")
            }
        ):
            entities.append(PsnMediaPlayerEntity(coordinator, platform))
            devices_added.add(platform)
    if entities:
        async_add_entities(entities)

    remove_listener = coordinator.async_add_listener(add_entities)
    add_entities()


class PsnMediaPlayerEntity(
    CoordinatorEntity[PlaystationNetworkCoordinator], MediaPlayerEntity
):
    """Media player entity representing currently playing game."""

    _attr_media_image_remotely_accessible = True
    _attr_media_content_type = MediaType.GAME
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_translation_key = "playstation"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: PlaystationNetworkCoordinator, platform: PlatformType
    ) -> None:
        """Initialize PSN MediaPlayer."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{platform.value}"
        self.key = platform
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=PLATFORM_MAP[platform],
            manufacturer="Sony Interactive Entertainment",
            model=PLATFORM_MAP[platform],
            via_device=(DOMAIN, coordinator.config_entry.unique_id),
        )

    @property
    def state(self) -> MediaPlayerState:
        """Media Player state getter."""
        session = self.coordinator.data.active_sessions.get(self.key)
        if session and session.status == "online":
            if self.coordinator.data.available and session.title_id is not None:
                return MediaPlayerState.PLAYING
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        """Media title getter."""
        session = self.coordinator.data.active_sessions.get(self.key)
        return session.title_name if session else None

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        session = self.coordinator.data.active_sessions.get(self.key)
        return session.title_id if session else None

    @property
    def media_image_url(self) -> str | None:
        """Media image url getter."""
        session = self.coordinator.data.active_sessions.get(self.key)
        return session.media_image_url if session else None
