"""Media player platform for Marantz IR integration."""

from dataclasses import dataclass
from typing import Any

from infrared_protocols.codes.marantz.pm6006 import MarantzPM6006Code

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
from .const import CONF_INFRARED_ENTITY_ID, CONF_MODEL, MarantzModel
from .entity import MarantzIrEntity

PARALLEL_UPDATES = 1

SOURCE_TO_CODE: dict[str, MarantzPM6006Code] = {
    "cd": MarantzPM6006Code.SOURCE_CD,
    "coax": MarantzPM6006Code.SOURCE_COAX,
    "network": MarantzPM6006Code.SOURCE_NETWORK,
    "optical": MarantzPM6006Code.SOURCE_OPTICAL,
    "phono": MarantzPM6006Code.SOURCE_PHONO,
    "recorder": MarantzPM6006Code.SOURCE_CDR,
    "tuner": MarantzPM6006Code.SOURCE_TUNER,
}

_PM6006_AMPLIFIER_MODELS = {MarantzModel.GENERIC_AMPLIFIER, MarantzModel.PM6006}


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
    model = MarantzModel(entry.data[CONF_MODEL])
    if model in _PM6006_AMPLIFIER_MODELS:
        async_add_entities([MarantzIrAmplifierMediaPlayer(entry, infrared_entity_id)])


class MarantzIrAmplifierMediaPlayer(MarantzIrEntity, MediaPlayerEntity, RestoreEntity):
    """Marantz IR amplifier media player entity."""

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

    def __init__(self, entry: MarantzIrConfigEntry, infrared_entity_id: str) -> None:
        """Initialize Marantz IR amplifier media player."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="media_player")

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
            if (source := data.get("source")) in SOURCE_TO_CODE:
                self._attr_source = source
            if (muted := data.get("is_volume_muted")) is not None:
                self._attr_is_volume_muted = bool(muted)

    async def async_turn_on(self) -> None:
        """Send the power toggle and assume the amplifier is now on.

        Marantz integrated amplifiers expose only a single POWER toggle
        over IR — there are no discrete on/off codes — so turn-on and
        turn-off send the same frame and rely on assumed_state.
        """
        await self._send_command(MarantzPM6006Code.POWER)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Send the power toggle and assume the amplifier is now off."""
        await self._send_command(MarantzPM6006Code.POWER)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_command(MarantzPM6006Code.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_command(MarantzPM6006Code.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_command(MarantzPM6006Code.MUTE)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._send_command(SOURCE_TO_CODE[source])
        self._attr_source = source
        self.async_write_ha_state()
