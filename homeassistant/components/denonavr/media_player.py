"""Support for Denon AVR receivers using their HTTP interface."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from denonavr import DenonAVR
from denonavr.const import POWER_ON, STATE_OFF, STATE_ON, STATE_PAUSED, STATE_PLAYING
from denonavr.exceptions import (
    AvrCommandError,
    AvrForbiddenError,
    AvrNetworkError,
    AvrTimoutError,
    DenonAvrError,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_COMMAND, CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CONF_RECEIVER
from .config_flow import (
    CONF_MANUFACTURER,
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
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.VOLUME_SET
)

SUPPORT_MEDIA_MODES = (
    MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.PLAY
)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1

# Services
SERVICE_GET_COMMAND = "get_command"
SERVICE_SET_DYNAMIC_EQ = "set_dynamic_eq"
SERVICE_UPDATE_AUDYSSEY = "update_audyssey"

_DenonDeviceT = TypeVar("_DenonDeviceT", bound="DenonDevice")
_R = TypeVar("_R")
_P = ParamSpec("_P")


DENON_STATE_MAPPING = {
    STATE_ON: MediaPlayerState.ON,
    STATE_OFF: MediaPlayerState.OFF,
    STATE_PLAYING: MediaPlayerState.PLAYING,
    STATE_PAUSED: MediaPlayerState.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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


def async_log_errors(
    func: Callable[Concatenate[_DenonDeviceT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_DenonDeviceT, _P], Coroutine[Any, Any, _R | None]]:
    """Log errors occurred when calling a Denon AVR receiver.

    Decorates methods of DenonDevice class.
    Declaration of staticmethod for this method is at the end of this class.
    """

    @wraps(func)
    async def wrapper(
        self: _DenonDeviceT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        # pylint: disable=protected-access
        available = True
        try:
            return await func(self, *args, **kwargs)
        except AvrTimoutError:
            available = False
            if self.available:
                _LOGGER.warning(
                    (
                        "Timeout connecting to Denon AVR receiver at host %s. "
                        "Device is unavailable"
                    ),
                    self._receiver.host,
                )
                self._attr_available = False
        except AvrNetworkError:
            available = False
            if self.available:
                _LOGGER.warning(
                    (
                        "Network error connecting to Denon AVR receiver at host %s. "
                        "Device is unavailable"
                    ),
                    self._receiver.host,
                )
                self._attr_available = False
        except AvrForbiddenError:
            available = False
            if self.available:
                _LOGGER.warning(
                    (
                        "Denon AVR receiver at host %s responded with HTTP 403 error. "
                        "Device is unavailable. Please consider power cycling your "
                        "receiver"
                    ),
                    self._receiver.host,
                )
                self._attr_available = False
        except AvrCommandError as err:
            available = False
            _LOGGER.error(
                "Command %s failed with error: %s",
                func.__name__,
                err,
            )
        except DenonAvrError as err:
            available = False
            _LOGGER.exception(
                "Error %s occurred in method %s for Denon AVR receiver",
                err,
                func.__name__,
            )
        finally:
            if available and not self.available:
                _LOGGER.info(
                    "Denon AVR receiver at host %s is available again",
                    self._receiver.host,
                )
                self._attr_available = True
        return None

    return wrapper


class DenonDevice(MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id: str,
        config_entry: ConfigEntry,
        update_audyssey: bool,
    ) -> None:
        """Initialize the device."""
        self._attr_unique_id = unique_id
        assert config_entry.unique_id
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{config_entry.data[CONF_HOST]}/",
            hw_version=config_entry.data[CONF_TYPE],
            identifiers={(DOMAIN, config_entry.unique_id)},
            manufacturer=config_entry.data[CONF_MANUFACTURER],
            model=config_entry.data[CONF_MODEL],
            name=receiver.name,
        )
        self._attr_sound_mode_list = receiver.sound_mode_list

        self._receiver = receiver
        self._update_audyssey = update_audyssey

        self._supported_features_base = SUPPORT_DENON
        self._supported_features_base |= (
            self._receiver.support_sound_mode
            and MediaPlayerEntityFeature.SELECT_SOUND_MODE
        )

        self._telnet_was_healthy: bool | None = None

    async def _telnet_callback(self, zone, event, parameter) -> None:
        """Process a telnet command callback."""
        # There are multiple checks implemented which reduce unnecessary updates of the ha state machine
        if zone != self._receiver.zone:
            return
        # Some updates trigger multiple events like one for artist and one for title for one change
        # We skip every event except the last one
        if event == "NSE" and not parameter.startswith("4"):
            return
        if event == "TA" and not parameter.startwith("ANNAME"):
            return
        if event == "HD" and not parameter.startswith("ALBUM"):
            return
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for telnet events."""
        self._receiver.register_callback("ALL", self._telnet_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the entity."""
        self._receiver.unregister_callback("ALL", self._telnet_callback)

    @async_log_errors
    async def async_update(self) -> None:
        """Get the latest status information from device."""
        receiver = self._receiver

        # We can only skip the update if telnet was healthy after
        # the last update and is still healthy now to ensure that
        # we don't miss any state changes while telnet is down
        # or reconnecting.
        if (
            telnet_is_healthy := receiver.telnet_connected and receiver.telnet_healthy
        ) and self._telnet_was_healthy:
            return

        # if async_update raises an exception, we don't want to skip the next update
        # so we set _telnet_was_healthy to None here and only set it to the value
        # before the update if the update was successful
        self._telnet_was_healthy = None

        await receiver.async_update()

        self._telnet_was_healthy = telnet_is_healthy

        if self._update_audyssey:
            await receiver.async_update_audyssey()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        return DENON_STATE_MAPPING.get(self._receiver.state)

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return self._receiver.input_func_list

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
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._receiver.sound_mode

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._receiver.input_func in self._receiver.netaudio_func_list:
            return self._supported_features_base | SUPPORT_MEDIA_MODES
        return self._supported_features_base

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return None

    @property
    def media_content_type(self) -> MediaType:
        """Content type of current playing media."""
        if self._receiver.state in {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}:
            return MediaType.MUSIC
        return MediaType.CHANNEL

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
    async def async_media_play_pause(self) -> None:
        """Play or pause the media player."""
        await self._receiver.async_toggle_play_pause()

    @async_log_errors
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._receiver.async_play()

    @async_log_errors
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._receiver.async_pause()

    @async_log_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._receiver.async_previous_track()

    @async_log_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._receiver.async_next_track()

    @async_log_errors
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        # Ensure that the AVR is turned on, which is necessary for input
        # switch to work.
        await self.async_turn_on()
        await self._receiver.async_set_input_func(source)

    @async_log_errors
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self._receiver.async_set_sound_mode(sound_mode)

    @async_log_errors
    async def async_turn_on(self) -> None:
        """Turn on media player."""
        await self._receiver.async_power_on()

    @async_log_errors
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._receiver.async_power_off()

    @async_log_errors
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._receiver.async_volume_up()

    @async_log_errors
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._receiver.async_volume_down()

    @async_log_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Volume has to be sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        volume_denon = float((volume * 100) - 80)
        if volume_denon > 18:
            volume_denon = float(18)
        await self._receiver.async_set_volume(volume_denon)

    @async_log_errors
    async def async_mute_volume(self, mute: bool) -> None:
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
