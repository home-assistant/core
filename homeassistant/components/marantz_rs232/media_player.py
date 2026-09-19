"""Media player platform for Marantz receivers using the 2007 protocol."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import math
from typing import Any, override

from marantz_rs232 import (
    MarantzV2007Receiver,
    V2007MainPlayer,
    V2007MultiRoomPlayer,
    V2007ReceiverState,
    V2007Source,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MarantzRS232ConfigEntry

PARALLEL_UPDATES = 1

MIN_VOLUME_DB = -80.0
VOLUME_DB_RANGE = 98.0

INPUT_SOURCE_TO_HA: dict[V2007Source, str] = {
    V2007Source.TV: "tv",
    V2007Source.DVD: "dvd",
    V2007Source.VCR1: "vcr1",
    V2007Source.VCR2: "vcr2",
    V2007Source.DSS_VCR2: "dss_vcr2",
    V2007Source.LD: "ld",
    V2007Source.USB: "usb",
    V2007Source.NETWORK: "network",
    V2007Source.AUX1: "aux1",
    V2007Source.AUX2: "aux2",
    V2007Source.SR4023_CD: "cd",
    V2007Source.CD_R: "cd_r",
    V2007Source.CD_CDR: "cd_cdr",
    V2007Source.TAPE: "tape",
    V2007Source.TUNER1: "tuner",
    V2007Source.FM1: "fm",
    V2007Source.AM1: "am",
    V2007Source.XM1: "xm",
    V2007Source.SIRIUS: "sirius",
    V2007Source.AM2: "am2",
    V2007Source.BD: "bd",
    V2007Source.MXPORT: "mxport",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MarantzRS232ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the receiver's main and multi-room players."""
    receiver = config_entry.runtime_data
    entities = [MarantzMediaPlayer(receiver, receiver.main, config_entry, "main")]
    if receiver.multi_room_a.power is not None:
        entities.append(
            MarantzMediaPlayer(
                receiver, receiver.multi_room_a, config_entry, "multi_room_a"
            )
        )
    async_add_entities(entities)


def _translate_errors[**_P, _R](
    func: Callable[_P, Awaitable[_R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Translate receiver communication failures into action errors."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except (ConnectionError, OSError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

    return wrapper


class MarantzMediaPlayer(MediaPlayerEntity):
    """Representation of a 2007-era Marantz receiver controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_translation_key = "receiver"
    _attr_should_poll = False

    _volume_min = MIN_VOLUME_DB
    _volume_range = VOLUME_DB_RANGE

    def __init__(
        self,
        receiver: MarantzV2007Receiver,
        player: V2007MainPlayer | V2007MultiRoomPlayer,
        config_entry: MarantzRS232ConfigEntry,
        zone: str,
    ) -> None:
        """Initialize the v2007 media player."""
        self._receiver = receiver
        self._player = player

        if isinstance(player, V2007MainPlayer):
            self._set_volume = player.set_volume
            self._volume_up = player.volume_up
            self._volume_down = player.volume_down
        else:
            self._set_volume = player.set_line_volume
            self._volume_up = player.line_volume_up
            self._volume_down = player.line_volume_down

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Marantz",
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"

        self._attr_source_list = sorted(INPUT_SOURCE_TO_HA.values())
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

        if zone == "main":
            self._attr_name = None
        else:
            self._attr_translation_key = "multi_room"

        self._async_update_from_player()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self.async_on_remove(self._receiver.subscribe(self._async_on_state_update))

    @callback
    def _async_on_state_update(self, state: V2007ReceiverState | None) -> None:
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_player()
        self.async_write_ha_state()

    @callback
    def _async_update_from_player(self) -> None:
        if self._player.power is None:
            self._attr_state = None
        else:
            self._attr_state = (
                MediaPlayerState.ON if self._player.power else MediaPlayerState.OFF
            )

        source = self._player.input_source
        self._attr_source = INPUT_SOURCE_TO_HA.get(source) if source else None

        if isinstance(self._player, V2007MainPlayer):
            volume = self._player.volume
        else:
            volume = self._player.line_volume

        if volume is not None and math.isfinite(volume):
            self._attr_volume_level = (volume - self._volume_min) / self._volume_range
        else:
            self._attr_volume_level = None

        self._attr_is_volume_muted = self._player.mute

    @override
    @_translate_errors
    async def async_turn_on(self) -> None:
        """Turn the receiver on."""
        await self._player.power_on()

    @override
    @_translate_errors
    async def async_turn_off(self) -> None:
        """Turn the receiver off."""
        await self._player.power_off()

    @override
    @_translate_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        db = volume * self._volume_range + self._volume_min
        await self._set_volume(db)

    @override
    @_translate_errors
    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._volume_up()

    @override
    @_translate_errors
    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._volume_down()

    @override
    @_translate_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        if mute:
            await self._player.mute_on()
        else:
            await self._player.mute_off()

    @override
    @_translate_errors
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        v2007_source = next(
            (ls for ls, ha_source in INPUT_SOURCE_TO_HA.items() if ha_source == source),
            None,
        )
        if v2007_source is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )

        await self._player.select_source(v2007_source)
