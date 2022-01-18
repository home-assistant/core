"""Support for Frontier Silicon Devices (Medion, Hama, Auna,...)."""
from __future__ import annotations

from datetime import datetime

from afsapi import AFSAPI, FSApiException, PlayState
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    REPEAT_MODE_OFF,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_OPENING,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SUPPORT_FRONTIER_SILICON = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SEEK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_REPEAT_SET
)

DEFAULT_PORT = 80
DEFAULT_PASSWORD = "1234"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Frontier Silicon entity."""

    afsapi = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AFSAPIDevice(config_entry, afsapi)], True)


class AFSAPIDevice(MediaPlayerEntity):
    """Representation of a Frontier Silicon device on the network."""

    def __init__(self, config_entry: ConfigEntry, afsapi: AFSAPI) -> None:
        """Initialize the Frontier Silicon API device."""
        self._afsapi = afsapi

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, afsapi.webfsapi_endpoint)},
            name=config_entry.title,
        )
        self._attr_media_content_type = MEDIA_TYPE_MUSIC
        self._attr_supported_features = SUPPORT_FRONTIER_SILICON

        self._attr_name = None
        self._attr_unique_id = None

        self._attr_source_list = None
        self._attr_source = None

        self._attr_sound_mode_list = None
        self._attr_sound_mode = None

        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None

        self._attr_source = None
        self._attr_is_volume_muted = None
        self._attr_media_image_url = None

        self._attr_media_position = None
        self._attr_media_position_updated_at = None

        self._attr_shuffle = None
        self._attr_repeat = None

        self._max_volume = None
        self._attr_volume_level = None

        self.__modes_by_label = None
        self.__sound_modes_by_label = None

    async def async_update(self):
        """Get the latest date and update device state."""
        afsapi = self._afsapi

        if not self._attr_name:
            self._attr_name = await afsapi.get_friendly_name()

        if not self._attr_unique_id:
            try:
                self._attr_unique_id = await afsapi.get_radio_id()
            except FSApiException:
                self._attr_unique_id = self._attr_name

        if not self._attr_source_list:
            self.__modes_by_label = {
                mode.label: mode.key for mode in await afsapi.get_modes()
            }
            self._attr_source_list = list(self.__modes_by_label.keys())

        if not self._attr_sound_mode_list:
            self.__sound_modes_by_label = {
                sound_mode.label: sound_mode.key
                for sound_mode in await afsapi.get_equalisers()
            }
            self._attr_sound_mode_list = list(self.__sound_modes_by_label.keys())

        # The API seems to include 'zero' in the number of steps (e.g. if the range is
        # 0-40 then get_volume_steps returns 41) subtract one to get the max volume.
        # If call to get_volume fails set to 0 and try again next time.
        if not self._max_volume:
            self._max_volume = int(await afsapi.get_volume_steps() or 1) - 1

        if await afsapi.get_power():
            status = await afsapi.get_play_status()
            self._attr_state = {
                PlayState.PLAYING: STATE_PLAYING,
                PlayState.PAUSED: STATE_PAUSED,
                PlayState.STOPPED: STATE_IDLE,
                PlayState.LOADING: STATE_OPENING,
                None: STATE_IDLE,
            }.get(status, STATE_UNKNOWN)
        else:
            self._attr_state = STATE_OFF

        if self._attr_state != STATE_OFF:
            info_name = await afsapi.get_play_name()
            info_text = await afsapi.get_play_text()

            self._attr_media_title = " - ".join(filter(None, [info_name, info_text]))
            self._attr_media_artist = await afsapi.get_play_artist()
            self._attr_media_album_name = await afsapi.get_play_album()

            self._attr_source = (await afsapi.get_mode()).label

            self._attr_sound_mode = (await afsapi.get_eq_preset()).label
            self._attr_is_volume_muted = await afsapi.get_mute()
            self._attr_media_image_url = await afsapi.get_play_graphic()

            self._attr_media_position = await afsapi.get_play_position()
            self._attr_media_position_updated_at = datetime.now()

            self._attr_shuffle = await afsapi.get_play_shuffle()
            self._attr_repeat = await afsapi.get_play_repeat()

            volume = await self._afsapi.get_volume()

            # Prevent division by zero if max_volume not known yet
            self._attr_volume_level = float(volume or 0) / (self._max_volume or 1)
        else:
            self._attr_media_title = None
            self._attr_media_artist = None
            self._attr_media_album_name = None

            self._attr_source = None

            self._attr_sound_mode = None
            self._attr_is_volume_muted = None
            self._attr_media_image_url = None

            self._attr_media_position = None
            self._attr_media_position_updated_at = None

            self._attr_shuffle = None
            self._attr_repeat = None

            self._attr_volume_level = None

    # Management actions
    # power control
    async def async_turn_on(self):
        """Turn on the device."""
        await self._afsapi.set_power(True)

    async def async_turn_off(self):
        """Turn off the device."""
        await self._afsapi.set_power(False)

    async def async_media_play(self):
        """Send play command."""
        await self._afsapi.play()

    async def async_media_pause(self):
        """Send pause command."""
        await self._afsapi.pause()

    async def async_media_play_pause(self):
        """Send play/pause command."""
        if self.state == STATE_PLAYING:
            await self._afsapi.pause()
        else:
            await self._afsapi.play()

    async def async_media_stop(self):
        """Send play/pause command."""
        await self._afsapi.pause()

    async def async_media_previous_track(self):
        """Send previous track command (results in rewind)."""
        await self._afsapi.rewind()

    async def async_media_next_track(self):
        """Send next track command (results in fast-forward)."""
        await self._afsapi.forward()

    async def async_media_seek(self, position):
        """Send seek command."""
        await self._afsapi.set_play_position(position)

    async def async_set_shuffle(self, shuffle):
        """Send shuffle command."""
        await self._afsapi.set_play_shuffle(shuffle)

    async def async_set_repeat(self, repeat):
        """Send repeat command."""
        await self._afsapi.set_play_repeat(repeat != REPEAT_MODE_OFF)

    # mute
    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self._afsapi.set_mute(mute)

    # volume
    async def async_volume_up(self):
        """Send volume up command."""
        volume = await self._afsapi.get_volume()
        volume = int(volume or 0) + 1
        await self._afsapi.set_volume(min(volume, self._max_volume))

    async def async_volume_down(self):
        """Send volume down command."""
        volume = await self._afsapi.get_volume()
        volume = int(volume or 0) - 1
        await self._afsapi.set_volume(max(volume, 0))

    async def async_set_volume_level(self, volume):
        """Set volume command."""
        if self._max_volume:  # Can't do anything sensible if not set
            volume = int(volume * self._max_volume)
            await self._afsapi.set_volume(volume)

    async def async_select_source(self, source):
        """Select input source."""
        await self._afsapi.set_power(True)
        await self._afsapi.set_mode(self.__modes_by_label.get(source))

    async def async_select_sound_mode(self, sound_mode):
        """Select EQ Preset."""
        await self._afsapi.set_eq_preset(self.__sound_modes_by_label[sound_mode])
