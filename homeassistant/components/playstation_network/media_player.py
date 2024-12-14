"""Media player entity for the Playstation Network Integration."""

import logging

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlaystationNetworkCoordinator
from .entity import PlaystationNetworkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Media Player Entity Setup."""
    coordinator: PlaystationNetworkCoordinator = config_entry.runtime_data

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
        remove_listener()

    remove_listener = coordinator.async_add_listener(add_entities)
    add_entities()


class MediaPlayer(PlaystationNetworkEntity, MediaPlayerEntity):
    """Media player entity representing currently playing game."""

    entity_description = MediaPlayerEntityDescription(
        key="console",
        translation_key="console",
        device_class=MediaPlayerDeviceClass.RECEIVER,
    )
    _attr_media_image_remotely_accessible = True
    _attr_translation_key = "playstation"
    _attr_media_content_type = MediaType.GAME

    def __init__(
        self, coordinator: PlaystationNetworkCoordinator, platform: str
    ) -> None:
        """Initialize PSN MediaPlayer."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{platform}_{self.entity_description.key}"
        self._active_platform = self.coordinator.data.platform.get("platform", "")
        self._media_player_platform = platform

    @property
    def state(self) -> MediaPlayerState:
        """Media Player state getter."""
        if self._active_platform == self._media_player_platform:
            match self.coordinator.data.platform.get("onlineStatus", ""):
                case "online":
                    if (
                        self.coordinator.data.available is True
                        and self.coordinator.data.title_metadata.get("npTitleId")
                        is not None
                    ):
                        return MediaPlayerState.PLAYING
                    return MediaPlayerState.ON
                case "offline":
                    return MediaPlayerState.OFF
                case _:
                    return MediaPlayerState.OFF
        return MediaPlayerState.OFF

    @property
    def name(self) -> str:
        """Name getter."""
        return f"{self._media_player_platform.upper()} Console"

    @property
    def media_title(self) -> str | None:
        """Media title getter."""
        if (
            self.coordinator.data.title_metadata.get("npTitleId")
            and self._active_platform == self._media_player_platform
        ):
            return self.coordinator.data.title_metadata.get("titleName")
        return None

    @property
    def media_image_url(self) -> str | None:
        """Media image url getter."""
        if (
            self.coordinator.data.title_metadata.get("npTitleId")
            and self._active_platform == self._media_player_platform
        ):
            title = self.coordinator.data.title_metadata
            if title.get("format", "").casefold() == "ps5":
                return title.get("conceptIconUrl")

            if title.get("format", "").casefold() == "ps4":
                return title.get("npTitleIconUrl")
        return None

    @property
    def is_on(self) -> bool:
        """Is user available on the Playstation Network."""
        return (
            self.coordinator.data.available is True
            and self._active_platform == self._media_player_platform
        )
