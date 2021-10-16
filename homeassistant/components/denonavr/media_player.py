"""Support for Denon AVR receivers using their HTTP interface."""
from __future__ import annotations

from collections.abc import Coroutine
from datetime import timedelta
from functools import wraps
import logging

from denonavr import DenonAVR
from denonavr.const import POWER_ON
from denonavr.exceptions import (
    AvrCommandError,
    AvrForbiddenError,
    AvrNetworkError,
    AvrTimoutError,
    DenonAvrError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import ATTR_COMMAND, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from . import CONF_RECEIVER
from .config_flow import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_TYPE,
    CONF_UPDATE_AUDYSSEY,
    DEFAULT_UPDATE_AUDYSSEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SOUND_MODE_RAW = "sound_mode_raw"
ATTR_DYNAMIC_EQ = "dynamic_eq"

SUPPORT_DENON = (
    SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_SET
)

SUPPORT_MEDIA_MODES = (
    SUPPORT_PLAY_MEDIA
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_VOLUME_SET
    | SUPPORT_PLAY
)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1

# Services
SERVICE_GET_COMMAND = "get_command"
SERVICE_SET_DYNAMIC_EQ = "set_dynamic_eq"
SERVICE_UPDATE_AUDYSSEY = "update_audyssey"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: entity_platform.EntityPlatform.async_add_entities,
):
    """Set up the DenonAVR receiver from a config entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    receiver = data[CONF_RECEIVER]
    update_audyssey = config_entry.options.get(
        CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY
    )
    for receiver_zone in receiver.zones.values():
        if config_entry.data[CONF_SERIAL_NUMBER] is not None:
            unique_id = f"{config_entry.unique_id}-{receiver_zone.zone}"
        else:
            unique_id = f"{config_entry.entry_id}-{receiver_zone.zone}"
        await receiver_zone.async_setup()
        entities.append(
            DenonDevice(
                receiver_zone,
                unique_id,
                config_entry,
                update_audyssey,
            )
        )
    _LOGGER.debug(
        "%s receiver at host %s initialized", receiver.manufacturer, receiver.host
    )

    # Register additional services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_GET_COMMAND,
        {vol.Required(ATTR_COMMAND): cv.string},
        f"async_{SERVICE_GET_COMMAND}",
    )
    platform.async_register_entity_service(
        SERVICE_SET_DYNAMIC_EQ,
        {vol.Required(ATTR_DYNAMIC_EQ): cv.boolean},
        f"async_{SERVICE_SET_DYNAMIC_EQ}",
    )
    platform.async_register_entity_service(
        SERVICE_UPDATE_AUDYSSEY,
        {},
        f"async_{SERVICE_UPDATE_AUDYSSEY}",
    )

    async_add_entities(entities, update_before_add=True)


class DenonDevice(MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id: str,
        config_entry: config_entries.ConfigEntry,
        update_audyssey: bool,
    ) -> None:
        """Initialize the device."""
        self._receiver = receiver
        self._unique_id = unique_id
        self._config_entry = config_entry
        self._update_audyssey = update_audyssey

        self._supported_features_base = SUPPORT_DENON
        self._supported_features_base |= (
            self._receiver.support_sound_mode and SUPPORT_SELECT_SOUND_MODE
        )
        self._available = True

    def async_log_errors(
        func: Coroutine,
    ) -> Coroutine:
        """
        Log errors occurred when calling a Denon AVR receiver.

        Decorates methods of DenonDevice class.
        Declaration of staticmethod for this method is at the end of this class.
        """

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # pylint: disable=protected-access
            available = True
            try:
                return await func(self, *args, **kwargs)
            except AvrTimoutError:
                available = False
                if self._available is True:
                    _LOGGER.warning(
                        "Timeout connecting to Denon AVR receiver at host %s. Device is unavailable",
                        self._receiver.host,
                    )
                    self._available = False
            except AvrNetworkError:
                available = False
                if self._available is True:
                    _LOGGER.warning(
                        "Network error connecting to Denon AVR receiver at host %s. Device is unavailable",
                        self._receiver.host,
                    )
                    self._available = False
            except AvrForbiddenError:
                available = False
                if self._available is True:
                    _LOGGER.warning(
                        "Denon AVR receiver at host %s responded with HTTP 403 error. Device is unavailable. Please consider power cycling your receiver",
                        self._receiver.host,
                    )
                    self._available = False
            except AvrCommandError as err:
                _LOGGER.error(
                    "Command %s failed with error: %s",
                    func.__name__,
                    err,
                )
            except DenonAvrError as err:
                _LOGGER.error(
                    "Error %s occurred in method %s for Denon AVR receiver",
                    err,
                    func.__name__,
                    exc_info=True,
                )
            finally:
                if available is True and self._available is False:
                    _LOGGER.info(
                        "Denon AVR receiver at host %s is available again",
                        self._receiver.host,
                    )
                    self._available = True

        return wrapper

    @async_log_errors
    async def async_update(self) -> None:
        """Get the latest status information from device."""
        await self._receiver.async_update()
        if self._update_audyssey:
            await self._receiver.async_update_audyssey()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self):
        """Return the unique id of the zone."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info of the receiver."""
        if self._config_entry.data[CONF_SERIAL_NUMBER] is None:
            return None

        device_info = {
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
            "manufacturer": self._config_entry.data[CONF_MANUFACTURER],
            "name": self._config_entry.title,
            "model": f"{self._config_entry.data[CONF_MODEL]}-{self._config_entry.data[CONF_TYPE]}",
        }

        return device_info

    @property
    def name(self):
        """Return the name of the device."""
        return self._receiver.name

    @property
    def state(self):
        """Return the state of the device."""
        return self._receiver.state

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._receiver.muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        # Volume is sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        if self._receiver.volume is None:
            return None
        return (float(self._receiver.volume) + 80) / 100

    @property
    def source(self):
        """Return the current input source."""
        return self._receiver.input_func

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return self._receiver.input_func_list

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._receiver.sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self._receiver.sound_mode_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._receiver.input_func in self._receiver.netaudio_func_list:
            return self._supported_features_base | SUPPORT_MEDIA_MODES
        return self._supported_features_base

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._receiver.state in (STATE_PLAYING, STATE_PAUSED):
            return MEDIA_TYPE_MUSIC
        return MEDIA_TYPE_CHANNEL

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._receiver.input_func in self._receiver.playing_func_list:
            return self._receiver.image_url
        return None

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._receiver.input_func not in self._receiver.playing_func_list:
            return self._receiver.input_func
        if self._receiver.title is not None:
            return self._receiver.title
        return self._receiver.frequency

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if self._receiver.artist is not None:
            return self._receiver.artist
        return self._receiver.band

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        if self._receiver.album is not None:
            return self._receiver.album
        return self._receiver.station

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return None

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return None

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        return None

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        return None

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        return None

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        if self._receiver.power != POWER_ON:
            return {}
        state_attributes = {}
        if (
            self._receiver.sound_mode_raw is not None
            and self._receiver.support_sound_mode
        ):
            state_attributes[ATTR_SOUND_MODE_RAW] = self._receiver.sound_mode_raw
        if self._receiver.dynamic_eq is not None:
            state_attributes[ATTR_DYNAMIC_EQ] = self._receiver.dynamic_eq
        return state_attributes

    @property
    def dynamic_eq(self):
        """Status of DynamicEQ."""
        return self._receiver.dynamic_eq

    @async_log_errors
    async def async_media_play_pause(self):
        """Play or pause the media player."""
        await self._receiver.async_toggle_play_pause()

    @async_log_errors
    async def async_media_play(self):
        """Send play command."""
        await self._receiver.async_play()

    @async_log_errors
    async def async_media_pause(self):
        """Send pause command."""
        await self._receiver.async_pause()

    @async_log_errors
    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._receiver.async_previous_track()

    @async_log_errors
    async def async_media_next_track(self):
        """Send next track command."""
        await self._receiver.async_next_track()

    @async_log_errors
    async def async_select_source(self, source: str):
        """Select input source."""
        # Ensure that the AVR is turned on, which is necessary for input
        # switch to work.
        await self.async_turn_on()
        await self._receiver.async_set_input_func(source)

    @async_log_errors
    async def async_select_sound_mode(self, sound_mode: str):
        """Select sound mode."""
        await self._receiver.async_set_sound_mode(sound_mode)

    @async_log_errors
    async def async_turn_on(self):
        """Turn on media player."""
        await self._receiver.async_power_on()

    @async_log_errors
    async def async_turn_off(self):
        """Turn off media player."""
        await self._receiver.async_power_off()

    @async_log_errors
    async def async_volume_up(self):
        """Volume up the media player."""
        await self._receiver.async_volume_up()

    @async_log_errors
    async def async_volume_down(self):
        """Volume down media player."""
        await self._receiver.async_volume_down()

    @async_log_errors
    async def async_set_volume_level(self, volume: int):
        """Set volume level, range 0..1."""
        # Volume has to be sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        volume_denon = float((volume * 100) - 80)
        if volume_denon > 18:
            volume_denon = float(18)
        await self._receiver.async_set_volume(volume_denon)

    @async_log_errors
    async def async_mute_volume(self, mute: bool):
        """Send mute command."""
        await self._receiver.async_mute(mute)

    @async_log_errors
    async def async_get_command(self, command: str, **kwargs):
        """Send generic command."""
        return await self._receiver.async_get_command(command)

    @async_log_errors
    async def async_update_audyssey(self):
        """Get the latest audyssey information from device."""
        await self._receiver.async_update_audyssey()

    @async_log_errors
    async def async_set_dynamic_eq(self, dynamic_eq: bool):
        """Turn DynamicEQ on or off."""
        if dynamic_eq:
            await self._receiver.async_dynamic_eq_on()
        else:
            await self._receiver.async_dynamic_eq_off()

        if self._update_audyssey:
            await self._receiver.async_update_audyssey()

    # Decorator defined before is a staticmethod
    async_log_errors = staticmethod(  # pylint: disable=no-staticmethod-decorator
        async_log_errors
    )
