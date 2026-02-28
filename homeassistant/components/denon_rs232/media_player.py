"""Media player platform for the Denon RS232 integration."""

from __future__ import annotations

from collections.abc import Callable
import logging

from denon_rs232 import (
    MIN_VOLUME_DB,
    VOLUME_DB_RANGE,
    DenonReceiver,
    DenonState,
    InputSource,
    PowerState,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DenonRS232ConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SOURCE_BY_NAME: dict[str, InputSource] = {s.value: s for s in InputSource}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonRS232ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Denon RS232 media player."""
    receiver = config_entry.runtime_data
    async_add_entities([DenonRS232MediaPlayer(receiver, config_entry)])


class DenonRS232MediaPlayer(MediaPlayerEntity):
    """Representation of a Denon receiver controlled over RS232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        receiver: DenonReceiver,
        config_entry: DenonRS232ConfigEntry,
    ) -> None:
        """Initialize the media player."""
        self._receiver = receiver
        self._attr_unique_id = config_entry.entry_id

        model = receiver.model
        model_name = model.name if model else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Denon",
            model=model_name,
            name="Denon Receiver",
        )

        if model:
            self._attr_source_list = sorted(s.value for s in model.input_sources)
            self._attr_sound_mode_list = list(model.surround_modes)
        else:
            self._attr_source_list = sorted(s.value for s in InputSource)
            self._attr_sound_mode_list = None

        self._unsub: Callable[[], None] | None = None
        self._update_from_state(receiver.state)

    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self._unsub = self._receiver.subscribe(self._on_state_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from receiver state updates."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _on_state_update(self, state: DenonState | None) -> None:
        """Handle a state update from the receiver."""
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._update_from_state(state)
        self.async_write_ha_state()

    def _update_from_state(self, state: DenonState) -> None:
        """Update entity attributes from a DenonState snapshot."""
        if state.power == PowerState.ON:
            self._attr_state = MediaPlayerState.ON
        elif state.power == PowerState.STANDBY:
            self._attr_state = MediaPlayerState.OFF
        else:
            self._attr_state = None

        if state.volume is not None:
            self._attr_volume_level = (state.volume - MIN_VOLUME_DB) / VOLUME_DB_RANGE
        else:
            self._attr_volume_level = None

        self._attr_is_volume_muted = state.mute

        if state.input_source is not None:
            self._attr_source = state.input_source.value
        else:
            self._attr_source = None

        self._attr_sound_mode = state.surround_mode

    async def async_turn_on(self) -> None:
        """Turn the receiver on."""
        await self._receiver.power_on()

    async def async_turn_off(self) -> None:
        """Turn the receiver off."""
        await self._receiver.power_standby()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        db = volume * VOLUME_DB_RANGE + MIN_VOLUME_DB
        await self._receiver.set_volume(db)

    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._receiver.volume_up()

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._receiver.volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        if mute:
            await self._receiver.mute_on()
        else:
            await self._receiver.mute_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if input_source := SOURCE_BY_NAME.get(source):
            await self._receiver.select_input_source(input_source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self._receiver.set_surround_mode(sound_mode)
