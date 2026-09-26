"""Support for Denon AVR receivers using their HTTP interface."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate, override

from denonavr import DenonAVR
from denonavr.const import (
    ALL_TELNET_EVENTS,
    ALL_ZONES,
    POWER_ON,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STOPPED,
)
from denonavr.exceptions import (
    AvrCommandError,
    AvrForbiddenError,
    AvrIncompleteResponseError,
    AvrInvalidResponseError,
    AvrNetworkError,
    AvrProcessingError,
    AvrTimoutError,
    DenonAvrError,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DenonavrConfigEntry
from .const import (
    ATTR_DYNAMIC_EQ,
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    TELNET_EVENTS,
)
from .coordinator import (
    UNAVAILABLE_ON,
    DenonAvrDataUpdateCoordinator,
    async_update_zone_audyssey,
    mark_unavailable,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SOUND_MODE_RAW = "sound_mode_raw"

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
    | MediaPlayerEntityFeature.STOP
)

PARALLEL_UPDATES = 1

DENON_STATE_MAPPING = {
    STATE_ON: MediaPlayerState.ON,
    STATE_OFF: MediaPlayerState.OFF,
    STATE_PLAYING: MediaPlayerState.PLAYING,
    STATE_PAUSED: MediaPlayerState.PAUSED,
    STATE_STOPPED: MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonavrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DenonAVR receiver from a config entry."""
    entities = []
    data = config_entry.runtime_data
    receiver = data.receiver
    for receiver_zone in receiver.zones.values():
        if config_entry.data[CONF_SERIAL_NUMBER] is not None:
            unique_id = f"{config_entry.unique_id}-{receiver_zone.zone}"
        else:
            unique_id = f"{config_entry.entry_id}-{receiver_zone.zone}"
        entities.append(
            DenonDevice(
                data.coordinator,
                data.audyssey_coordinator,
                receiver_zone,
                unique_id,
                config_entry,
            )
        )
    _LOGGER.debug(
        "%s receiver at host %s initialized", receiver.manufacturer, receiver.host
    )

    async_add_entities(entities)


def async_log_errors[_DenonDeviceT: DenonDevice, **_P, _R](
    func: Callable[Concatenate[_DenonDeviceT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_DenonDeviceT, _P], Coroutine[Any, Any, _R | None]]:
    """Log command errors and refresh the coordinator after success.

    The entity has should_poll=False, so nothing else refreshes it after a
    successful command. A connectivity failure marks the coordinator
    unavailable at once rather than leaving stale data looking current.
    """

    @wraps(func)
    async def wrapper(
        self: _DenonDeviceT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        async with self.coordinator.lock:
            # Read before the call: an Audyssey-scoped command marks the
            # coordinators unavailable itself before re-raising.
            was_available = self.available
            try:
                result = await func(self, *args, **kwargs)
            except AvrTimoutError as err:
                if was_available:
                    _LOGGER.warning(
                        "Timeout connecting to Denon AVR receiver at host %s: %s",
                        self._receiver.host,
                        err,
                    )
                mark_unavailable(self.coordinator)
                return None
            except AvrNetworkError as err:
                if was_available:
                    _LOGGER.warning(
                        "Network error connecting to Denon AVR receiver at host %s: %s",
                        self._receiver.host,
                        err,
                    )
                mark_unavailable(self.coordinator)
                return None
            except AvrProcessingError as err:
                if was_available:
                    _LOGGER.warning(
                        "Update of Denon AVR receiver at host %s not complete: %s",
                        self._receiver.host,
                        err,
                    )
                return None
            except AvrForbiddenError as err:
                if was_available:
                    _LOGGER.warning(
                        (
                            "Denon AVR receiver at host %s responded with HTTP 403"
                            " error. Please consider power cycling your receiver: %s"
                        ),
                        self._receiver.host,
                        err,
                    )
                mark_unavailable(self.coordinator)
                return None
            except (AvrInvalidResponseError, AvrIncompleteResponseError) as err:
                if was_available:
                    _LOGGER.warning(
                        "Denon AVR receiver at host %s returned malformed response: %s",
                        self._receiver.host,
                        err,
                    )
                mark_unavailable(self.coordinator)
                return None
            except AvrCommandError as err:
                _LOGGER.error(
                    "Command %s failed with error: %s",
                    func.__name__,
                    err,
                )
                return None
            except DenonAvrError:
                _LOGGER.exception(
                    "Error occurred in method %s for Denon AVR receiver", func.__name__
                )
                return None
        await self.coordinator.async_request_refresh()
        return result

    return wrapper


class DenonDevice(CoordinatorEntity[DenonAvrDataUpdateCoordinator], MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(
        self,
        coordinator: DenonAvrDataUpdateCoordinator,
        audyssey_coordinator: DenonAvrDataUpdateCoordinator,
        receiver: DenonAVR,
        unique_id: str,
        config_entry: DenonavrConfigEntry,
    ) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self._audyssey_coordinator = audyssey_coordinator
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{config_entry.data[CONF_HOST]}/",
            hw_version=config_entry.data[CONF_TYPE],
            identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
            manufacturer=config_entry.data[CONF_MANUFACTURER],
            model=config_entry.data[CONF_MODEL],
            name=receiver.name,
        )
        self._attr_sound_mode_list = receiver.sound_mode_list
        self._receiver = receiver

        self._supported_features_base = SUPPORT_DENON
        self._supported_features_base |= (
            self._receiver.support_sound_mode
            and MediaPlayerEntityFeature.SELECT_SOUND_MODE
        )

    def _telnet_callback(self, zone: str, event: str, parameter: str) -> None:
        """Process a telnet command callback."""
        # There are multiple checks implemented which reduce
        # unnecessary updates of the ha state machine
        if zone not in (self._receiver.zone, ALL_ZONES):
            return
        if event not in TELNET_EVENTS:
            return
        # Some updates trigger multiple events like one for
        # artist and one for title for one change.
        # We skip every event except the last one.
        if event == "NSE" and not parameter.startswith("4"):
            return
        if event == "TA" and not parameter.startswith("ANNAME"):
            return
        if event == "HD" and not parameter.startswith("ALBUM"):
            return
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register for coordinator updates and telnet events."""
        await super().async_added_to_hass()
        # super() subscribes to the status coordinator only, but dynamic_eq
        # is Audyssey-scoped and would otherwise go stale.
        self.async_on_remove(
            self._audyssey_coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )
        self._receiver.register_callback(ALL_TELNET_EVENTS, self._telnet_callback)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clean up the entity."""
        if self._receiver.telnet_connected:
            await self._receiver.async_telnet_disconnect()
        self._receiver.unregister_callback(ALL_TELNET_EVENTS, self._telnet_callback)

    @override
    async def async_update(self) -> None:
        """Refresh now, so update_entity returns after the read.

        Skipped while Telnet is healthy. Reads every zone once per targeted
        entity: unlike the Audyssey query, status reads are fast.
        """
        if not self.enabled:
            return
        await self.coordinator.async_refresh()

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        return DENON_STATE_MAPPING.get(self._receiver.state)

    @property
    @override
    def source_list(self) -> list[str]:
        """Return a list of available input sources."""
        return self._receiver.input_func_list

    @property
    @override
    def is_volume_muted(self) -> bool:
        """Return boolean if volume is currently muted."""
        return self._receiver.muted

    @property
    @override
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        # Volume is sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        if self._receiver.volume is None:
            return None
        return (float(self._receiver.volume) + 80) / 100

    @property
    @override
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.input_func

    @property
    @override
    def sound_mode(self) -> str | None:
        """Return the current matched sound mode."""
        return self._receiver.sound_mode

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._receiver.input_func in self._receiver.netaudio_func_list:
            return self._supported_features_base | SUPPORT_MEDIA_MODES
        return self._supported_features_base

    @property
    @override
    def media_content_type(self) -> MediaType:
        """Content type of current playing media."""
        if self._receiver.state in {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}:
            return MediaType.MUSIC
        return MediaType.CHANNEL

    @property
    @override
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self._receiver.input_func in self._receiver.playing_func_list:
            return self._receiver.image_url
        return None

    @property
    @override
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._receiver.input_func not in self._receiver.playing_func_list:
            return self._receiver.input_func
        if self._receiver.title is not None:
            return self._receiver.title
        return self._receiver.frequency

    @property
    @override
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if self._receiver.artist is not None:
            return self._receiver.artist
        return self._receiver.band

    @property
    @override
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if self._receiver.album is not None:
            return self._receiver.album
        return self._receiver.station

    @property
    @override
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

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_media_play_pause(self) -> None:
        """Play or pause the media player."""
        await self._receiver.async_toggle_play_pause()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._receiver.async_play()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._receiver.async_pause()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._receiver.async_stop()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._receiver.async_previous_track()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._receiver.async_next_track()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._receiver.async_set_input_func(source)

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self._receiver.async_set_sound_mode(sound_mode)

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_turn_on(self) -> None:
        """Turn on media player."""
        await self._receiver.async_power_on()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._receiver.async_power_off()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._receiver.async_volume_up()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._receiver.async_volume_down()

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Volume has to be sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        volume_denon = float((volume * 100) - 80)
        if volume_denon > 18:
            volume_denon = float(18)
        await self._receiver.async_set_volume(volume_denon)

    # pylint: disable-next=home-assistant-action-swallowed-exception
    @async_log_errors
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._receiver.async_mute(mute)

    @async_log_errors
    async def async_get_command(self, command: str, **kwargs: Any) -> str:
        """Send generic command."""
        return await self._receiver.async_get_command(command)

    @async_log_errors
    async def async_update_audyssey(self) -> None:
        """Get the latest audyssey information from device.

        This zone alone, not through the coordinator: as an entity service
        it is already called once per zone, so refreshing every zone each
        time would square these slow queries.
        """
        try:
            await async_update_zone_audyssey(self._receiver)
        except UNAVAILABLE_ON:
            # Audyssey-scoped, so that coordinator's data is suspect too.
            mark_unavailable(self._audyssey_coordinator)
            raise
        # Keeps last_update_success and the Audyssey entities in step with
        # a fetch made outside the coordinator. Not async_set_updated_data():
        # that cancels the refresh set_dynamic_eq queued for the other zones.
        self._audyssey_coordinator.last_update_success = True
        self._audyssey_coordinator.async_update_listeners()

    @async_log_errors
    async def async_set_dynamic_eq(self, dynamic_eq: bool) -> None:
        """Turn DynamicEQ on or off."""
        try:
            if dynamic_eq:
                await self._receiver.async_dynamic_eq_on()
            else:
                await self._receiver.async_dynamic_eq_off()
        except UNAVAILABLE_ON:
            # An Audyssey-scoped command, so that coordinator's data cannot
            # be trusted either, not just the general one the decorator marks.
            mark_unavailable(self._audyssey_coordinator)
            raise

        # The option governs the recurring poll alone. Safe inside the
        # decorator's lock: async_request_refresh() only schedules.
        await self._audyssey_coordinator.async_request_refresh()
