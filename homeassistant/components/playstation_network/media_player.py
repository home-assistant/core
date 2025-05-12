"""Media player entity for the PlayStation Network Integration."""

import logging

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
from .const import DOMAIN, PlatformType
from .helpers import SessionData

_LOGGER = logging.getLogger(__name__)


PLATFORM_MAP = {
    PlatformType.PS5: "PlayStation 5",
    PlatformType.PS4: "PlayStation 4",
    PlatformType.PS3: "PlayStation 3",
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
    supported_devices = {PlatformType.PS5, PlatformType.PS4, PlatformType.PS3}
    device_reg = dr.async_get(hass)
    entities = []

    @callback
    def add_entities() -> None:
        nonlocal devices_added

        if not supported_devices - devices_added:
            remove_listener()

        for console in coordinator.data.active_sessions:
            if (platform := console.platform) and (
                platform_type := PlatformType(platform)
            ) not in devices_added:
                async_add_entities([PsnMediaPlayerEntity(coordinator, platform_type)])
                devices_added.add(platform_type)

    for platform in supported_devices:
        if device_reg.async_get_device(
            identifiers={(DOMAIN, f"{coordinator.config_entry.unique_id}_{platform}")}
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

        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{platform}"
        self.key = platform
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=PLATFORM_MAP[platform],
            manufacturer="Sony Interactive Entertainment",
            model=PLATFORM_MAP[platform],
        )

    @property
    def state(self) -> MediaPlayerState:
        """Media Player state getter."""
        session = next(
            (
                session
                for session in self.coordinator.data.active_sessions
                if session.platform == self.key
            ),
            SessionData(),
        )
        if session.status == "online":
            if self.coordinator.data.available and session.title_id is not None:
                return MediaPlayerState.PLAYING
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        """Media title getter."""
        session = next(
            (
                session
                for session in self.coordinator.data.active_sessions
                if session.platform == self.key
            ),
            SessionData(),
        )
        return session.title_name

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        session = next(
            (
                session
                for session in self.coordinator.data.active_sessions
                if session.platform == self.key
            ),
            SessionData(),
        )
        return session.title_id

    @property
    def media_image_url(self) -> str | None:
        """Media image url getter."""
        session = next(
            (
                session
                for session in self.coordinator.data.active_sessions
                if session.platform == self.key
            ),
            SessionData(),
        )
        return session.media_image_url
