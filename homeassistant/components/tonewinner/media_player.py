"""Tonewinner AT-500 media player."""

import asyncio
import contextlib
import logging
from typing import override

from tonewinner_rs232 import SOUND_MODE_LABELS, ReceiverState, TonewinnerReceiver

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TonewinnerConfigEntry
from .const import CONF_SOURCE_MAPPINGS, DOMAIN

_LOGGER = logging.getLogger(__name__)


INPUT_SOURCES = {
    "HDMI 1": "HD1",
    "HDMI 2": "HD2",
    "HDMI 3": "HD3",
    "HDMI 4": "HD4",
    "HDMI 5": "HD5",
    "HDMI 6": "HD6",
    "Optical 1": "OP1",
    "Optical 2": "OP2",
    "Coaxial 1": "CO1",
    "Coaxial 2": "CO2",
    "Analog 1": "AN1",
    "Analog 2": "AN2",
    "Analog 3": "AN3",
    "Bluetooth": "BT",
    "USB": "USB",
    "PC": "PC",
    "HDMI eARC": "ARC",
}

SOUND_MODES = {label: code for code, label in SOUND_MODE_LABELS.items()}

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TonewinnerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player entity."""
    receiver = config_entry.runtime_data
    entity = TonewinnerMediaPlayer(hass, config_entry, receiver)
    async_add_entities([entity])


class TonewinnerMediaPlayer(MediaPlayerEntity):
    """Tonewinner AT-500 media player."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
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

    _source_check_task: asyncio.Task[None] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TonewinnerConfigEntry,
        receiver: TonewinnerReceiver,
    ) -> None:
        """Initialize the media player."""
        self.hass = hass
        self._receiver = receiver
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Tonewinner",
            model="AT-500",
        )
        self._attr_available = False

        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_source = None
        self._attr_sound_mode = None
        self._was_off = True

        self._source_code_to_custom_name: dict[str, str] = {}
        self._custom_name_to_source_code: dict[str, str] = {}
        source_mappings = entry.options.get(CONF_SOURCE_MAPPINGS, {})
        self._attr_source_list = []
        for source_name, source_code in INPUT_SOURCES.items():
            mapping = source_mappings.get(source_code, {})
            if not mapping.get("enabled", True):
                continue
            custom_name = mapping.get("name", source_name)
            self._source_code_to_custom_name[source_code] = custom_name
            self._custom_name_to_source_code[custom_name] = source_code
            self._attr_source_list.append(custom_name)

        self._attr_sound_mode_list = list(SOUND_MODES.keys())

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to state changes when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(self._receiver.subscribe(self._on_state_change))
        self._apply_state(self._receiver.state)

    @callback
    def _on_state_change(self, state: ReceiverState | None) -> None:
        """Handle state changes from the receiver."""
        if state is None:
            _LOGGER.warning("Connection to the Tonewinner receiver was lost")
            self._attr_available = False
            self.async_write_ha_state()
            return
        self._apply_state(state)

    @callback
    def _apply_state(self, state: ReceiverState) -> None:
        """Apply receiver state to HA entity attributes."""
        self._attr_available = True

        if state.power is not None:
            new_state = MediaPlayerState.ON if state.power else MediaPlayerState.OFF
            # Update state before creating tasks: the eager asyncio task
            # factory starts the coroutine immediately.
            self._attr_state = new_state
            if new_state == MediaPlayerState.ON and self._was_off:
                self._was_off = False
                self.hass.async_create_task(self._query_input_source())
            elif new_state == MediaPlayerState.OFF:
                self._attr_source = None
                self._was_off = True

        if state.volume is not None:
            self._attr_volume_level = state.volume / 100.0

        if state.mute is not None:
            self._attr_is_volume_muted = state.mute

        if state.source_name is not None:
            self._attr_source = self._resolve_source(
                state.source_name, state.audio_source
            )

        if state.sound_mode_label is not None:
            self._attr_sound_mode = state.sound_mode_label

        if state.power and not self._attr_source and not self._source_check_task:
            task = self.hass.async_create_task(self._periodic_source_check())
            # With the eager asyncio task factory the coroutine may already
            # have run to completion (and cleared itself) by the time the
            # task is returned.
            if not task.done():
                self._source_check_task = task

        self.async_write_ha_state()

    def _resolve_source(self, source_name: str, audio_source: str | None) -> str | None:
        """Resolve a device source name to the configured display name."""
        if source_name == "eARC/ARC":
            source_name = "ARC"

        if source_name in self._custom_name_to_source_code:
            return source_name

        source_code = None
        for default_name, code in INPUT_SOURCES.items():
            if default_name.lower() == source_name.lower() or code == source_name:
                source_code = code
                break

        if source_code and source_code in self._source_code_to_custom_name:
            return self._source_code_to_custom_name[source_code]

        if audio_source and audio_source in self._source_code_to_custom_name:
            return self._source_code_to_custom_name[audio_source]

        return source_name

    async def _query_input_source(self) -> None:
        """Query device for current input source."""
        if self._attr_state != MediaPlayerState.ON:
            return
        await self._receiver.query_source()
        await asyncio.sleep(0.2)

    async def _periodic_source_check(self) -> None:
        """Periodically check for input source when device is ON but source unknown."""
        max_attempts = 5
        for _attempt in range(max_attempts):
            if self._attr_source:
                break
            await self._query_input_source()
            await asyncio.sleep(3)
        self._source_check_task = None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._source_check_task:
            self._source_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._source_check_task

    async def send_raw_command(self, command: str) -> None:
        """Send a raw command to the receiver."""
        if not self._receiver.connected:
            raise HomeAssistantError("Not connected")

        if command.startswith("0x"):
            try:
                data = bytes(int(token, 16) for token in command.split())
            except ValueError as err:
                raise HomeAssistantError(f"Invalid hex command: {command}") from err
            try:
                command = data.decode("ascii")
            except UnicodeDecodeError as err:
                msg = f"Hex command contains non-ASCII bytes: {command}"
                raise HomeAssistantError(msg) from err
        await self._receiver.send_command(command)

    # --- Media player controls ---

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._receiver.power_on()

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._receiver.power_off()
        self._attr_state = MediaPlayerState.OFF
        self._attr_source = None
        self._was_off = True
        self.async_write_ha_state()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (HA 0.0-1.0, device 0-80)."""
        vol_device = min(volume * 100.0, 80)
        await self._receiver.set_volume(vol_device)
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._receiver.volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._receiver.volume_down()

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        if mute:
            await self._receiver.mute_on()
        else:
            await self._receiver.mute_off()

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source not in self._custom_name_to_source_code:
            raise HomeAssistantError(f"Unknown source: {source}")

        source_code = self._custom_name_to_source_code[source]
        await self._receiver.select_source(source_code)

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        if sound_mode not in SOUND_MODES:
            raise HomeAssistantError(f"Unknown sound mode: {sound_mode}")
        mode_code = SOUND_MODES[sound_mode]
        await self._receiver.select_sound_mode(mode_code)
