"""Tonewinner media player."""

import logging
from typing import override

from tonewinner_rs232 import INPUT_SOURCE_NAMES, SOUND_MODE_LABELS, ReceiverState

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TonewinnerConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INPUT_SOURCES = {name: code for code, name in INPUT_SOURCE_NAMES.items()}

SOUND_MODES: dict[str, str] = {}
for _code, _label in SOUND_MODE_LABELS.items():
    # First wins so firmware misspellings (DITECT, ALLSTREO) never shadow
    # the canonical codes.
    SOUND_MODES.setdefault(_label, _code)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TonewinnerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player entity."""
    async_add_entities([TonewinnerMediaPlayer(config_entry)])


class TonewinnerMediaPlayer(MediaPlayerEntity):
    """Tonewinner media player."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: TonewinnerConfigEntry) -> None:
        """Initialize the media player."""
        self._entry = entry
        self._receiver = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Tonewinner",
            model=entry.data.get(CONF_MODEL),
        )
        self._attr_available = False

        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_source = None
        self._attr_sound_mode = None

        self._attr_source_list = list(INPUT_SOURCES)
        self._attr_sound_mode_list = list(SOUND_MODES)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to state changes when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(self._receiver.subscribe(self._on_state_change))
        if self._receiver.connected:
            self._apply_state(self._receiver.state)
        else:
            self.hass.config_entries.async_schedule_reload(self._entry.entry_id)

    @callback
    def _on_state_change(self, state: ReceiverState | None) -> None:
        """Handle state changes from the receiver."""
        if state is None:
            if self._attr_available:
                _LOGGER.info("Connection to the Tonewinner receiver was lost")
                self._attr_available = False
                # The library never reconnects on its own; reload instead so
                # HA's retry loop restores the connection. Schedule through
                # hass so the entry does not track (and wait on) this task.
                self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
        else:
            if not self._attr_available:
                _LOGGER.info("Connection to the Tonewinner receiver was restored")
            self._apply_state(state)
        self.async_write_ha_state()

    @callback
    def _apply_state(self, state: ReceiverState) -> None:
        """Apply receiver state to HA entity attributes."""
        self._attr_available = True

        if state.power is not None:
            self._attr_state = (
                MediaPlayerState.ON if state.power else MediaPlayerState.OFF
            )
            if not state.power:
                self._attr_source = None

        if state.volume is not None:
            self._attr_volume_level = state.volume / 80

        if state.mute is not None:
            self._attr_is_volume_muted = state.mute

        # The library retains the last known source across power transitions;
        # while powered down no input is active, so do not surface it.
        if state.source_name is not None and state.power is not False:
            self._attr_source = self._resolve_source(
                state.source_name, state.audio_source
            )

        if state.sound_mode_label is not None:
            self._attr_sound_mode = state.sound_mode_label

    def _resolve_source(self, source_name: str, audio_source: str | None) -> str | None:
        """Resolve a device-reported source name to a display name."""
        if source_name == "eARC/ARC":
            source_name = "ARC"

        for name, code in INPUT_SOURCES.items():
            if source_name.lower() in (name.lower(), code.lower()):
                return name

        if audio_source in INPUT_SOURCE_NAMES:
            return INPUT_SOURCE_NAMES[audio_source]

        return source_name

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        try:
            await self._receiver.power_on()
        except OSError as err:
            raise HomeAssistantError(f"Failed to turn on: {err}") from err

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        try:
            await self._receiver.power_off()
        except OSError as err:
            raise HomeAssistantError(f"Failed to turn off: {err}") from err
        self._attr_state = MediaPlayerState.OFF
        self._attr_source = None
        self.async_write_ha_state()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (HA 0.0-1.0, device 0-80 in half steps).

        Snapping to the half-step grid keeps the device echo equal to what we
        sent, so the slider does not jump after an off-grid value is rounded
        by the firmware.
        """
        try:
            await self._receiver.set_volume(round(volume * 160) / 2)
        except OSError as err:
            raise HomeAssistantError(f"Failed to set volume: {err}") from err
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Volume up."""
        try:
            await self._receiver.volume_up()
        except OSError as err:
            raise HomeAssistantError(f"Failed to step volume up: {err}") from err

    @override
    async def async_volume_down(self) -> None:
        """Volume down."""
        try:
            await self._receiver.volume_down()
        except OSError as err:
            raise HomeAssistantError(f"Failed to step volume down: {err}") from err

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        command = self._receiver.mute_on if mute else self._receiver.mute_off
        try:
            await command()
        except OSError as err:
            action = "mute" if mute else "unmute"
            raise HomeAssistantError(f"Failed to {action}: {err}") from err

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source not in INPUT_SOURCES:
            raise HomeAssistantError(f"Unknown source: {source}")

        try:
            await self._receiver.select_source(INPUT_SOURCES[source])
        except OSError as err:
            raise HomeAssistantError(
                f"Failed to select source {source}: {err}"
            ) from err

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        if sound_mode not in SOUND_MODES:
            raise HomeAssistantError(f"Unknown sound mode: {sound_mode}")
        try:
            await self._receiver.select_sound_mode(SOUND_MODES[sound_mode])
        except OSError as err:
            raise HomeAssistantError(
                f"Failed to select sound mode {sound_mode}: {err}"
            ) from err
