"""Media player platform for NAD Infrared integration."""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.codes.nad.amplifier import NADAmplifierCode
from infrared_protocols.codes.nad.cd import NADCDCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import CONF_DEVICE_TYPE, NADDeviceType
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
    "tuner": NADAmplifierCode.TUNER,
}


@dataclass
class _NadReceiverExtraData(ExtraStoredData):
    """Persisted assumed-state data for a NAD receiver.

    Stored separately from the entity state because while the receiver is
    OFF, ``MediaPlayerEntity.state_attributes`` strips ``source``, so a
    restart in the OFF state would otherwise lose it.
    """

    source: str | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Serialize for the restore-state store."""
        return {"source": self.source}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NAD Infrared media player from config entry."""
    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type in (NADDeviceType.RECEIVER, NADDeviceType.AMPLIFIER):
        async_add_entities([NadIrReceiverMediaPlayer(entry)])
    elif device_type == NADDeviceType.CD_PLAYER:
        async_add_entities([NadIrCDPlayerMediaPlayer(entry)])


class NadIrReceiverMediaPlayer(NadIrEntity, MediaPlayerEntity, RestoreEntity):
    """NAD Infrared receiver or amplifier media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_translation_key = "receiver"
    _attr_source_list = list(SOURCE_TO_CODE)
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize NAD Infrared receiver media player."""
        super().__init__(entry, unique_id_suffix="media_player")

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Persist source regardless of ON/OFF state."""
        return _NadReceiverExtraData(source=self._attr_source)

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known assumed state and source."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None and (
            last_state.state in (MediaPlayerState.ON, MediaPlayerState.OFF)
        ):
            self._attr_state = MediaPlayerState(last_state.state)

        if (extra := await self.async_get_last_extra_data()) is not None and (
            source := extra.as_dict().get("source")
        ) in SOURCE_TO_CODE:
            self._attr_source = source

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
        await self._send_nad_command(SOURCE_TO_CODE[source])
        self._attr_source = source
        self.async_write_ha_state()


class NadIrCDPlayerMediaPlayer(NadIrEntity, MediaPlayerEntity):
    """NAD Infrared CD player media player entity.

    NAD CD player remotes have no discrete power codes, so only playback is
    controlled here.
    """

    _attr_name = None
    _attr_assumed_state = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize NAD Infrared CD player media player."""
        super().__init__(entry, unique_id_suffix="media_player")

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_nad_command(NADCDCode.PLAY)
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_nad_command(NADCDCode.PAUSE)
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_nad_command(NADCDCode.STOP)
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    @override
    async def async_media_next_track(self) -> None:
        """Send skip forward command."""
        await self._send_nad_command(NADCDCode.SKIP_FORWARD)

    @override
    async def async_media_previous_track(self) -> None:
        """Send skip back command."""
        await self._send_nad_command(NADCDCode.SKIP_BACK)
