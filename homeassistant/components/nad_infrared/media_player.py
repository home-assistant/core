"""Media player platform for NAD Infrared integration."""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.codes.nad.amplifier import NADAmplifierCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import NadIrConfigEntry
from .const import DOMAIN
from .entity import NadIrEntity

PARALLEL_UPDATES = 1

SOURCE_TO_CODE: dict[str, NADAmplifierCode] = {
    "input_1": NADAmplifierCode.INPUT_1,
    "input_2": NADAmplifierCode.INPUT_2,
    "input_3": NADAmplifierCode.INPUT_3,
    "input_4": NADAmplifierCode.INPUT_4,
    "input_5": NADAmplifierCode.INPUT_5,
    "input_6": NADAmplifierCode.INPUT_6,
    "input_7": NADAmplifierCode.INPUT_7,
    "front": NADAmplifierCode.FRONT,
    "mp": NADAmplifierCode.MP,
    "tuner": NADAmplifierCode.TUNER,
}

SOUND_MODE_TO_CODE: dict[str, NADAmplifierCode] = {
    "pliix_movie": NADAmplifierCode.PLIIX_MOVIE,
    "pliix_music": NADAmplifierCode.PLIIX_MUSIC,
    "dolby_surround_ex": NADAmplifierCode.DOLBY_SURROUND_EX,
    "neo6_cinema": NADAmplifierCode.NEO6_CINEMA,
    "neo6_music": NADAmplifierCode.NEO6_MUSIC,
    "matrix_7_1": NADAmplifierCode.MATRIX_7_1,
    "ears": NADAmplifierCode.EARS,
    "enhanced_stereo": NADAmplifierCode.ENHANCED_STEREO_1,
    "stereo_downmix": NADAmplifierCode.STEREO_DOWNMIX,
    "direct": NADAmplifierCode.DIRECT,
    "bypass": NADAmplifierCode.BYPASS,
}


@dataclass
class _NadReceiverExtraData(ExtraStoredData):
    """Persisted assumed-state data for a NAD receiver.

    Stored separately from the entity state because while the receiver is
    OFF, ``MediaPlayerEntity.state_attributes`` strips ``source`` and
    ``sound_mode``, so a restart in the OFF state would otherwise lose them.
    The power state is stored too, because the entity state is saved as
    unavailable when the emitter is unavailable at shutdown.
    """

    power_state: MediaPlayerState | None
    source: str | None
    sound_mode: str | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Serialize for the restore-state store."""
        return {
            "power_state": self.power_state,
            "source": self.source,
            "sound_mode": self.sound_mode,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NadIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NAD Infrared media player from config entry."""
    async_add_entities([NadIrReceiverMediaPlayer(entry)])


class NadIrReceiverMediaPlayer(NadIrEntity, MediaPlayerEntity, RestoreEntity):
    """NAD Infrared receiver or amplifier media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_translation_key = "receiver"
    _attr_source_list = list(SOURCE_TO_CODE)
    _attr_sound_mode_list = list(SOUND_MODE_TO_CODE)
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )

    def __init__(self, entry: NadIrConfigEntry) -> None:
        """Initialize NAD Infrared receiver media player."""
        super().__init__(entry, unique_id_suffix="media_player")

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Persist power state, source and sound mode."""
        return _NadReceiverExtraData(
            power_state=self._attr_state,
            source=self._attr_source,
            sound_mode=self._attr_sound_mode,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known assumed state, source and sound mode."""
        await super().async_added_to_hass()

        if (extra := await self.async_get_last_extra_data()) is not None:
            data = extra.as_dict()
            if (power_state := data.get("power_state")) in (
                MediaPlayerState.ON,
                MediaPlayerState.OFF,
            ):
                self._attr_state = MediaPlayerState(power_state)
            if (source := data.get("source")) in SOURCE_TO_CODE:
                self._attr_source = source
            if (sound_mode := data.get("sound_mode")) in SOUND_MODE_TO_CODE:
                self._attr_sound_mode = sound_mode

    @override
    async def async_turn_on(self) -> None:
        """Send discrete power-on command."""
        await self._send_nad_command(NADAmplifierCode.ON)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Send discrete power-off command."""
        await self._send_nad_command(NADAmplifierCode.OFF)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_nad_command(NADAmplifierCode.VOLUME_UP)

    @override
    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_nad_command(NADAmplifierCode.VOLUME_DOWN)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute toggle command.

        NAD receivers only have a mute toggle, so the mute state is not tracked.
        """
        await self._send_nad_command(NADAmplifierCode.MUTE)

    @override
    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        if (code := SOURCE_TO_CODE.get(source)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": source,
                    "valid_sources": ", ".join(SOURCE_TO_CODE),
                },
            )
        await self._send_nad_command(code)
        self._attr_source = source
        self.async_write_ha_state()

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a listening mode."""
        if (code := SOUND_MODE_TO_CODE.get(sound_mode)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_mode",
                translation_placeholders={
                    "invalid_sound_mode": sound_mode,
                    "valid_sound_modes": ", ".join(SOUND_MODE_TO_CODE),
                },
            )
        await self._send_nad_command(code)
        self._attr_sound_mode = sound_mode
        self.async_write_ha_state()
