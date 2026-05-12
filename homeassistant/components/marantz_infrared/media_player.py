"""Media player platform for Marantz IR integration."""

from dataclasses import dataclass
from typing import Any

from infrared_protocols.codes.marantz.audio import MarantzAudioCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import MarantzIrConfigEntry
from .const import CONF_INFRARED_ENTITY_ID, CONF_MODEL, MODELS
from .entity import MarantzIrEntity

PARALLEL_UPDATES = 1

SOURCE_TO_CODE: dict[str, MarantzAudioCode] = {
    "cd": MarantzAudioCode.SOURCE_CD,
    "coax": MarantzAudioCode.SOURCE_COAX,
    "laserdisc": MarantzAudioCode.SOURCE_LD,
    "md": MarantzAudioCode.SOURCE_MD,
    "network": MarantzAudioCode.SOURCE_NETWORK,
    "optical": MarantzAudioCode.SOURCE_OPTICAL,
    "phono": MarantzAudioCode.SOURCE_PHONO,
    "recorder": MarantzAudioCode.SOURCE_CDR,
    "satellite": MarantzAudioCode.SOURCE_SAT,
    "tape": MarantzAudioCode.SOURCE_TAPE,
    "tuner": MarantzAudioCode.SOURCE_TUNER,
    "tv": MarantzAudioCode.SOURCE_TV,
    "vcr": MarantzAudioCode.SOURCE_VCR1,
}


@dataclass
class _MarantzAmplifierExtraData(ExtraStoredData):
    """Persisted assumed-state data for a Marantz amplifier.

    Stored separately from the entity state because while the amplifier is
    OFF, ``MediaPlayerEntity.state_attributes`` strips ``source`` / mute,
    so a restart in the OFF state would otherwise lose them.
    """

    source: str | None
    is_volume_muted: bool | None

    def as_dict(self) -> dict[str, Any]:
        """Serialize for the restore-state store."""
        return {"source": self.source, "is_volume_muted": self.is_volume_muted}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarantzIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marantz IR media player from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    lib_model = MODELS[entry.data[CONF_MODEL]]
    if MarantzAudioCode.POWER in lib_model.codes:
        async_add_entities([MarantzIrAmplifierMediaPlayer(entry, infrared_entity_id)])


class MarantzIrAmplifierMediaPlayer(MarantzIrEntity, MediaPlayerEntity, RestoreEntity):
    """Marantz IR amplifier media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_translation_key = "receiver"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: MarantzIrConfigEntry, infrared_entity_id: str) -> None:
        """Initialize Marantz IR amplifier media player."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="media_player")
        codes = MODELS[entry.data[CONF_MODEL]].codes
        self._source_to_code = {
            source: code for source, code in SOURCE_TO_CODE.items() if code in codes
        }
        self._attr_source_list = list(self._source_to_code)

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Persist source and mute regardless of ON/OFF state."""
        return _MarantzAmplifierExtraData(
            source=self._attr_source,
            is_volume_muted=self._attr_is_volume_muted,
        )

    async def async_added_to_hass(self) -> None:
        """Restore last known assumed state, source, and mute."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None and (
            last_state.state in (MediaPlayerState.ON, MediaPlayerState.OFF)
        ):
            self._attr_state = MediaPlayerState(last_state.state)

        if (extra := await self.async_get_last_extra_data()) is not None:
            data = extra.as_dict()
            if (source := data.get("source")) in self._source_to_code:
                self._attr_source = source
            if (muted := data.get("is_volume_muted")) is not None:
                self._attr_is_volume_muted = bool(muted)

    async def async_turn_on(self) -> None:
        """Send the power toggle and assume the amplifier is now on.

        Marantz integrated amplifiers expose only a single POWER toggle
        over IR — there are no discrete on/off codes — so turn-on and
        turn-off send the same frame and rely on assumed_state.
        """
        await self._send_command(MarantzAudioCode.POWER)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Send the power toggle and assume the amplifier is now off."""
        await self._send_command(MarantzAudioCode.POWER)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_command(MarantzAudioCode.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_command(MarantzAudioCode.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_command(MarantzAudioCode.MUTE)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._send_command(self._source_to_code[source])
        self._attr_source = source
        self.async_write_ha_state()
