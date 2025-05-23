"""Support for Denon AVR receivers using their HTTP interface."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, Concatenate

from denonavr import DenonAVR
from denonavr.const import (
    ALL_TELNET_EVENTS,
    ALL_ZONES,
    POWER_ON,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from denonavr.exceptions import (
    AvrCommandError,
    AvrForbiddenError,
    AvrNetworkError,
    AvrProcessingError,
    AvrTimoutError,
    DenonAvrError,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import ATTR_COMMAND, CONF_HOST, CONF_MODEL, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DenonavrConfigEntry
from .const import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
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

# HA Telnet events
TELNET_EVENTS = {
    "HD",
    "MS",
    "MU",
    "MV",
    "NS",
    "NSE",
    "PS",
    "SI",
    "SS",
    "TF",
    "ZM",
    "Z2",
    "Z3",
}

DENON_STATE_MAPPING = {
    STATE_ON: MediaPlayerState.ON,
    STATE_OFF: MediaPlayerState.OFF,
    STATE_PLAYING: MediaPlayerState.PLAYING,
    STATE_PAUSED: MediaPlayerState.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonavrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DenonAVR receiver from a config entry."""
    entities = []
    receiver = config_entry.runtime_data
    update_audyssey = config_entry.options.get(
        CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY
    )
    for receiver_zone in receiver.zones.values():
        if config_entry.data[CONF_SERIAL_NUMBER] is not None:
            unique_id = f"{config_entry.unique_id}-{receiver_zone.zone}"
        else:
            unique_id = f"{config_entry.entry_id}-{receiver_zone.zone}"
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
        None,
        f"async_{SERVICE_UPDATE_AUDYSSEY}",
    )

    async_add_entities(entities, update_before_add=True)


def async_log_errors[_DenonDeviceT: DenonDevice, **_P, _R](
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
        except AvrProcessingError:
            available = True
            if self.available:
                _LOGGER.warning(
                    (
                        "Update of Denon AVR receiver at host %s not complete. "
                        "Device is still available"
                    ),
                    self._receiver.host,
                )
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
        except DenonAvrError:
            available = False
            _LOGGER.exception(
                "Error occurred in method %s for Denon AVR receiver", func.__name__
            )
        finally:
            if available and not self.available:
                _LOGGER.warning(
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
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id: str,
        config_entry: DenonavrConfigEntry,
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

    async def _telnet_callback(self, zone: str, event: str, parameter: str) -> None:
        """Process a telnet command callback."""
        # There are multiple checks implemented which reduce unnecessary updates of the ha state machine
        if zone not in (self._receiver.zone, ALL_ZONES):
            return
        if event not in TELNET_EVENTS:
            return
        # Some updates trigger multiple events like one for artist and one for title for one change
        # We skip every event except the last one
        if event == "NSE" and not parameter.startswith("4"):
            return
        if event == "TA" and not parameter.startswith("ANNAME"):
            return
        if event == "HD" and not parameter.startswith("ALBUM"):
            return
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for telnet events."""
        self._receiver.register_callback(ALL_TELNET_EVENTS, self._telnet_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the entity."""
        if self._receiver.telnet_connected:
            await self._receiver.async_telnet_disconnect()
        self._receiver.unregister_callback(ALL_TELNET_EVENTS, self._telnet_callback)

    @async_log_errors
    async def async_update(self) -> None:
        """Get the latest status information from device."""
        receiver = self._receiver

        # We skip the update if telnet is healthy.
        # When telnet recovers it automatically updates all properties.
        if receiver.telnet_connected and receiver.telnet_healthy:
            return

        await receiver.async_update()

        if self._update_audyssey:
            await receiver.async_update_audyssey()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        return DENON_STATE_MAPPING.get(self._receiver.state)

    @property
    def source_list(self) -> list[str]:
        """Return a list of available input sources."""
        return self._receiver.input_func_list

    @property
    def is_volume_muted(self) -> bool:
        """Return boolean if volume is currently muted."""
        return self._receiver.muted

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        # Volume is sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        if self._receiver.volume is None:
            return None
        return (float(self._receiver.volume) + 80) / 100

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.input_func

    @property
    def sound_mode(self) -> str | None:
        """Return the current matched sound mode."""
        return self._receiver.sound_mode

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._receiver.input_func in self._receiver.netaudio_func_list:
            return self._supported_features_base | SUPPORT_MEDIA_MODES
        return self._supported_features_base

    @property
    def media_content_type(self) -> MediaType:
        """Content type of current playing media."""
        if self._receiver.state in {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}:
            return MediaType.MUSIC
        return MediaType.CHANNEL

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self._receiver.input_func in self._receiver.playing_func_list:
            return self._receiver.image_url
        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._receiver.input_func not in self._receiver.playing_func_list:
            return self._receiver.input_func
        if self._receiver.title is not None:
            return self._receiver.title
        return self._receiver.frequency

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if self._receiver.artist is not None:
            return self._receiver.artist
        return self._receiver.band

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if self._receiver.album is not None:
            return self._receiver.album
        return self._receiver.station

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        receiver = self._receiver
        if receiver.power != POWER_ON:
            return {}
        state_attributes: dict[str, Any] = {}
        if (
            sound_mode_raw := receiver.sound_mode_raw
        ) is not None and receiver.support_sound_mode:
            state_attributes[ATTR_SOUND_MODE_RAW] = sound_mode_raw
        if (dynamic_eq := receiver.dynamic_eq) is not None:
            state_attributes[ATTR_DYNAMIC_EQ] = dynamic_eq
        return state_attributes

    @property
    def dynamic_eq(self) -> bool | None:
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
    async def async_get_command(self, command: str, **kwargs: Any) -> str:
        """Send generic command."""
        return await self._receiver.async_get_command(command)

    @async_log_errors
    async def async_update_audyssey(self) -> None:
        """Get the latest audyssey information from device."""
        await self._receiver.async_update_audyssey()

    @async_log_errors
    async def async_set_dynamic_eq(self, dynamic_eq: bool) -> None:
        """Turn DynamicEQ on or off."""
        if dynamic_eq:
            await self._receiver.async_dynamic_eq_on()
        else:
            await self._receiver.async_dynamic_eq_off()

        if self._update_audyssey:
            await self._receiver.async_update_audyssey()
