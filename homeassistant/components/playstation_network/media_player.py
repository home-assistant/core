"""Media player entity for the Playstation Network Integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlaystationNetworkCoordinator
from .coordinator import PlaystationNetworkData
from .entity import PlaystationNetworkEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class PSNdata:
    """PSN dataclass."""

    account = {"id": "", "handle": ""}
    presence = {"availability": "", "lastAvailableDate": ""}
    platform = {"status": "", "platform": ""}
    title = {"name": "", "format": "", "imageURL": None, "playing": False}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Media Player Entity Setup."""
    coordinator: PlaystationNetworkCoordinator = config_entry.runtime_data

    if coordinator.data.platform.get("platform") is None:
        username = coordinator.data.username
        _LOGGER.warning(
            "No console found associated with account: %s. -- Skipping creation of media player",
            username,
        )
        return

    async_add_entities([MediaPlayer(coordinator)])


class MediaPlayer(PlaystationNetworkEntity, MediaPlayerEntity):
    """Media player entity representing currently playing game."""

    device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: PlaystationNetworkCoordinator) -> None:
        """Initialize PSN MediaPlayer."""
        super().__init__(coordinator)
        self.psn: PlaystationNetworkData = self.coordinator.data
        self._attr_has_entity_name = True

    @property
    def icon(self) -> str:
        """Icon Getter."""
        return "mdi:sony-playstation"

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Is media image remotely accessible getter."""
        return True

    @property
    def state(self) -> MediaPlayerState:
        """Media Player state getter."""
        match self.psn.platform.get("onlineStatus", ""):
            case "online":
                if (
                    self.psn.available is True
                    and self.psn.title_metadata.get("npTitleId") is not None
                ):
                    return MediaPlayerState.PLAYING
                return MediaPlayerState.ON
            case "offline":
                return MediaPlayerState.OFF
            case _:
                return MediaPlayerState.OFF

    @property
    def unique_id(self) -> str:
        """Unique ID Getter."""
        return f"{self.psn.username.lower()}_{self.psn.platform.get('platform', "").lower()}_console"

    @property
    def name(self) -> str:
        """Name getter."""
        return f"{self.psn.platform.get('platform')} Console"

    @property
    def media_content_type(self) -> MediaType:
        """Content type of current playing media."""
        return MediaType.GAME

    @property
    def media_title(self) -> str | None:
        """Media title getter."""
        if self.psn.title_metadata.get("npTitleId"):
            return self.psn.title_metadata.get("titleName")
        if self.psn.platform.get("onlineStatus") == "online":
            return "Browsing the menu"
        return None

    @property
    def app_name(self) -> str:
        """App name getter."""
        return ""

    @property
    def media_image_url(self) -> str | None:
        """Media image url getter."""
        if self.psn.title_metadata.get("npTitleId"):
            title = self.psn.title_metadata
            if title.get("format", "").casefold() == "ps5":
                return title.get("conceptIconUrl")

            if title.get("format", "").casefold() == "ps4":
                return title.get("npTitleIconUrl")
        return None

    @property
    def is_on(self):
        """Is user available on the Playstation Network."""
        return self.psn.available is True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self.async_write_ha_state()
