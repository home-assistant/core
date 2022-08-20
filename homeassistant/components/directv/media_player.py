"""Support for the DirecTV receivers."""
from __future__ import annotations

import logging
from typing import Any

from directv import DIRECTV

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_MEDIA_CURRENTLY_RECORDING,
    ATTR_MEDIA_RATING,
    ATTR_MEDIA_RECORDED,
    ATTR_MEDIA_START_TIME,
    DOMAIN,
)
from .entity import DIRECTVEntity

_LOGGER = logging.getLogger(__name__)

KNOWN_MEDIA_TYPES = [MEDIA_TYPE_MOVIE, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW]

SUPPORT_DTV = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.PLAY
)

SUPPORT_DTV_CLIENT = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.PLAY
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DirecTV config entry."""
    dtv = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for location in dtv.device.locations:
        entities.append(
            DIRECTVMediaPlayer(
                dtv=dtv,
                name=str.title(location.name),
                address=location.address,
            )
        )

    async_add_entities(entities, True)


class DIRECTVMediaPlayer(DIRECTVEntity, MediaPlayerEntity):
    """Representation of a DirecTV receiver on the network."""

    def __init__(self, *, dtv: DIRECTV, name: str, address: str = "0") -> None:
        """Initialize DirecTV media player."""
        super().__init__(
            dtv=dtv,
            address=address,
        )

        self._attr_unique_id = self._device_id
        self._attr_name = name
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        self._attr_available = False

        self._is_recorded = None
        self._is_standby = True
        self._last_position = None
        self._last_update = None
        self._paused = None
        self._program = None

    async def async_update(self) -> None:
        """Retrieve latest state."""
        state = await self.dtv.state(self._address)
        self._attr_available = state.available
        self._is_standby = state.standby
        self._program = state.program

        if self._is_standby:
            self._attr_assumed_state = False
            self._is_recorded = None
            self._last_position = None
            self._last_update = None
            self._paused = None
        elif self._program is not None:
            self._paused = self._last_position == self._program.position
            self._is_recorded = self._program.recorded
            self._last_position = self._program.position
            self._last_update = state.at
            self._attr_assumed_state = self._is_recorded

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        if self._is_standby:
            return {}
        return {
            ATTR_MEDIA_CURRENTLY_RECORDING: self.media_currently_recording,
            ATTR_MEDIA_RATING: self.media_rating,
            ATTR_MEDIA_RECORDED: self.media_recorded,
            ATTR_MEDIA_START_TIME: self.media_start_time,
        }

    # MediaPlayerEntity properties and methods
    @property
    def state(self):
        """Return the state of the device."""
        if self._is_standby:
            return STATE_OFF

        # For recorded media we can determine if it is paused or not.
        # For live media we're unable to determine and will always return
        # playing instead.
        if self._paused:
            return STATE_PAUSED

        return STATE_PLAYING

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        if self._is_standby or self._program is None:
            return None

        return self._program.program_id

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if self._is_standby or self._program is None:
            return None

        if self._program.program_type in KNOWN_MEDIA_TYPES:
            return self._program.program_type

        return MEDIA_TYPE_MOVIE

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self._is_standby or self._program is None:
            return None

        return self._program.duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._is_standby:
            return None

        return self._last_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        if self._is_standby:
            return None

        return self._last_update

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_standby or self._program is None:
            return None

        if self.media_content_type == MEDIA_TYPE_MUSIC:
            return self._program.music_title

        return self._program.title

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if self._is_standby or self._program is None:
            return None

        return self._program.music_artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        if self._is_standby or self._program is None:
            return None

        return self._program.music_album

    @property
    def media_series_title(self):
        """Return the title of current episode of TV show."""
        if self._is_standby or self._program is None:
            return None

        return self._program.episode_title

    @property
    def media_channel(self):
        """Return the channel current playing media."""
        if self._is_standby or self._program is None:
            return None

        return f"{self._program.channel_name} ({self._program.channel})"

    @property
    def source(self):
        """Name of the current input source."""
        if self._is_standby or self._program is None:
            return None

        return self._program.channel

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_DTV_CLIENT if self._is_client else SUPPORT_DTV

    @property
    def media_currently_recording(self):
        """If the media is currently being recorded or not."""
        if self._is_standby or self._program is None:
            return None

        return self._program.recording

    @property
    def media_rating(self):
        """TV Rating of the current playing media."""
        if self._is_standby or self._program is None:
            return None

        return self._program.rating

    @property
    def media_recorded(self):
        """If the media was recorded or live."""
        if self._is_standby:
            return None

        return self._is_recorded

    @property
    def media_start_time(self):
        """Start time the program aired."""
        if self._is_standby or self._program is None:
            return None

        return dt_util.as_local(self._program.start_time)

    async def async_turn_on(self) -> None:
        """Turn on the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("Turn on %s", self.name)
        await self.dtv.remote("poweron", self._address)

    async def async_turn_off(self) -> None:
        """Turn off the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("Turn off %s", self.name)
        await self.dtv.remote("poweroff", self._address)

    async def async_media_play(self) -> None:
        """Send play command."""
        _LOGGER.debug("Play on %s", self.name)
        await self.dtv.remote("play", self._address)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        _LOGGER.debug("Pause on %s", self.name)
        await self.dtv.remote("pause", self._address)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        _LOGGER.debug("Stop on %s", self.name)
        await self.dtv.remote("stop", self._address)

    async def async_media_previous_track(self) -> None:
        """Send rewind command."""
        _LOGGER.debug("Rewind on %s", self.name)
        await self.dtv.remote("rew", self._address)

    async def async_media_next_track(self) -> None:
        """Send fast forward command."""
        _LOGGER.debug("Fast forward on %s", self.name)
        await self.dtv.remote("ffwd", self._address)

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Select input source."""
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_CHANNEL,
            )
            return

        _LOGGER.debug("Changing channel on %s to %s", self.name, media_id)
        await self.dtv.tune(media_id, self._address)
