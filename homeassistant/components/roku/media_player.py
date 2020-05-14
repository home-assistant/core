"""Support for the Roku media player."""
import logging
from typing import List

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import STATE_HOME, STATE_IDLE, STATE_PLAYING, STATE_STANDBY

from . import RokuDataUpdateCoordinator, RokuEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_ROKU = (
    SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Roku config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unique_id = coordinator.data.info.serial_number
    async_add_entities([RokuMediaPlayer(unique_id, coordinator)], True)


class RokuMediaPlayer(RokuEntity, MediaPlayerEntity):
    """Representation of a Roku media player on the network."""

    def __init__(self, unique_id: str, coordinator: RokuDataUpdateCoordinator) -> None:
        """Initialize the Roku device."""
        super().__init__(
            coordinator=coordinator,
            name=coordinator.data.info.name,
            device_id=unique_id,
        )

        self._unique_id = unique_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._unique_id

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self.coordinator.data.state.standby:
            return STATE_STANDBY

        if self.coordinator.data.app is None:
            return None

        if (
            self.coordinator.data.app.name == "Power Saver"
            or self.coordinator.data.app.screensaver
        ):
            return STATE_IDLE

        if self.coordinator.data.app.name == "Roku":
            return STATE_HOME

        if self.coordinator.data.app.name is not None:
            return STATE_PLAYING

        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ROKU

    @property
    def media_content_type(self) -> str:
        """Content type of current playing media."""
        if self.app_id is None or self.app_name in ("Power Saver", "Roku"):
            return None

        if self.app_id == "tvinput.dtv" and self.coordinator.data.channel is not None:
            return MEDIA_TYPE_CHANNEL

        return MEDIA_TYPE_APP

    @property
    def media_image_url(self) -> str:
        """Image url of current playing media."""
        if self.app_id is None or self.app_name in ("Power Saver", "Roku"):
            return None

        return self.coordinator.roku.app_icon_url(self.app_id)

    @property
    def app_name(self) -> str:
        """Name of the current running app."""
        if self.coordinator.data.app is not None:
            return self.coordinator.data.app.name

        return None

    @property
    def app_id(self) -> str:
        """Return the ID of the current running app."""
        if self.coordinator.data.app is not None:
            return self.coordinator.data.app.app_id

        return None

    @property
    def media_channel(self):
        """Return the TV channel currently tuned."""
        if self.app_id != "tvinput.dtv" or self.coordinator.data.channel is None:
            return None

        if self.coordinator.data.channel.name is not None:
            return f"{self.coordinator.data.channel.name} ({self.coordinator.data.channel.number})"

        return self.coordinator.data.channel.number

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self.app_id != "tvinput.dtv" or self.coordinator.data.channel is None:
            return None

        if self.coordinator.data.channel.program_title is not None:
            return self.coordinator.data.channel.program_title

        return None

    @property
    def source(self) -> str:
        """Return the current input source."""
        if self.coordinator.data.app is not None:
            return self.coordinator.data.app.name

        return None

    @property
    def source_list(self) -> List:
        """List of available input sources."""
        return ["Home"] + sorted(app.name for app in self.coordinator.data.apps)

    async def async_turn_on(self) -> None:
        """Turn on the Roku."""
        await self.coordinator.roku.remote("poweron")

    async def async_turn_off(self) -> None:
        """Turn off the Roku."""
        await self.coordinator.roku.remote("poweroff")

    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        await self.coordinator.roku.remote("play")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.roku.remote("reverse")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.roku.remote("forward")

    async def async_mute_volume(self, mute) -> None:
        """Mute the volume."""
        await self.coordinator.roku.remote("volume_mute")

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.coordinator.roku.remote("volume_up")

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.roku.remote("volume_down")

    async def async_play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        """Tune to channel."""
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_CHANNEL,
            )
            return

        await self.coordinator.roku.tune(media_id)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source == "Home":
            await self.coordinator.roku.remote("home")

        appl = next(
            (app for app in self.coordinator.data.apps if app.name == source), None
        )

        if appl is not None:
            await self.coordinator.roku.launch(appl.app_id)
