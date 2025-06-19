"""Support for Songpal-enabled (Sony) media devices."""

from __future__ import annotations

from collections import OrderedDict
import logging

from songpal import SongpalException
from songpal.containers import Input, Setting, Volume

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .base import SongpalBaseEntity
from .const import ERROR_REQUEST_RETRY
from .coordinator import SongpalCoordinator
from .device import device_unique_id
from .entities import create_entities_for_platform

_LOGGER = logging.getLogger(__name__)

INITIAL_RETRY_DELAY = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up songpal coordinator and entities."""

    create_entities_for_platform(
        hass, entry, SongpalMediaPlayerEntity, MEDIA_PLAYER_DOMAIN, async_add_entities
    )


class SongpalMediaPlayerEntity(MediaPlayerEntity, SongpalBaseEntity):
    """Class representing a Songpal device."""

    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, hass: HomeAssistant, coordinator: SongpalCoordinator) -> None:
        """Init."""

        self._coordinator = coordinator
        self._sysinfo = None
        self._model = None

        self._state = False
        self._attr_available = False
        self._initialized = False

        self._volume_control: Volume = None
        self._volume_min = 0
        self._volume_max = 1
        self._volume: int = 0
        self._attr_is_volume_muted = False

        self._active_source = None
        self._sources: OrderedDict[str, Input] = OrderedDict()
        self._active_sound_mode: Input = None
        self._sound_modes: dict[str, Setting] = {}

        super().__init__(hass, coordinator)

    def entity_name(self):
        """Return the name of this entity."""

        return "media_player"

    @property
    def unique_id(self) -> str:
        """Return unique ID (maintaining consistency with pre-coordinator unique ID)."""

        return device_unique_id(self.coordinator.data)

    def update_state(self, data) -> None:
        """Get state from coordinator."""

        if self._sysinfo is None:
            self._sysinfo = data["sysinfo"]

        if self._model is None:
            interface_info = data["interface_info"]
            self._model = interface_info.modelName

        if not self.coordinator.available:
            self._attr_available = False
            return

        volumes = data["volumes"]

        if len(volumes) > 1:
            _LOGGER.debug("Got %s volume controls, using the first one", volumes)

        volume: Volume = volumes[0]
        _LOGGER.debug("Current volume: %s", volume)

        self._volume_max = volume.maxVolume
        self._volume_min = volume.minVolume
        self._volume = volume.volume
        self._volume_control = volume
        self._attr_is_volume_muted = self._volume_control.is_muted

        status = data["power"]
        self._state = status.status
        _LOGGER.debug("Got state: %s", status)

        inputs = data["inputs"]
        _LOGGER.debug("Got ins: %s", inputs)

        playing_source_uri = data["play_info"][0].parentUri
        self._sources = OrderedDict()
        for input_ in inputs:
            self._sources[input_.uri] = input_
            if input_.uri == playing_source_uri:
                self._active_source = input_

        _LOGGER.debug("Active source: %s", self._active_source)

        (
            self._active_sound_mode,
            self._sound_modes,
        ) = self._get_sound_modes_info(data)

        self._attr_available = True

    def _get_sound_modes_info(self, data):
        """Get available sound modes and the active one."""
        for settings in data["sound_settings"]:
            if settings.target == "soundField":
                break
        else:
            return None, {}

        if isinstance(settings, Setting):
            settings = [settings]

        sound_modes = {}
        active_sound_mode = None
        for setting in settings:
            cur = setting.currentValue
            for opt in setting.candidate:
                if not opt.isAvailable:
                    continue
                if opt.value == cur:
                    active_sound_mode = opt.value
                sound_modes[opt.value] = opt

        _LOGGER.debug("Got sound modes: %s", sound_modes)
        _LOGGER.debug("Active sound mode: %s", active_sound_mode)

        return active_sound_mode, sound_modes

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        _LOGGER.debug("Calling set_sound_setting with %s: %s", name, value)
        await self.coordinator.device.set_sound_settings(name, value)

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        for out in self._sources.values():
            if out.title == source:
                await out.activate()
                return

        _LOGGER.error("Unable to find output: %s", source)

    @property
    def source_list(self) -> list[str]:
        """Return list of available sources."""
        return [src.title for src in self._sources.values()]

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        for mode in self._sound_modes.values():
            if mode.title == sound_mode:
                await self.coordinator.device.set_sound_settings(
                    "soundField", mode.value
                )
                return

        _LOGGER.error("Unable to find sound mode: %s", sound_mode)

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return list of available sound modes.

        When active mode is None it means that sound mode is unavailable on the sound bar.
        Can be due to incompatible sound bar or the sound bar is in a mode that does not
        support sound mode changes.
        """
        if not self._active_sound_mode:
            return None
        return [sound_mode.title for sound_mode in self._sound_modes.values()]

    @property
    def state(self) -> MediaPlayerState:
        """Return current state."""
        if self._state:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def source(self) -> str | None:
        """Return currently active source."""
        # Avoid a KeyError when _active_source is not (yet) populated
        return getattr(self._active_source, "title", None)

    @property
    def sound_mode(self) -> str | None:
        """Return currently active sound_mode."""
        active_sound_mode = self._sound_modes.get(self._active_sound_mode)
        return active_sound_mode.title if active_sound_mode else None

    @property
    def volume_level(self) -> float:
        """Return volume level."""
        return self._volume / self._volume_max

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        volume = int(volume * self._volume_max)
        _LOGGER.debug("Setting volume to %s", volume)
        return await self._volume_control.set_volume(volume)

    async def async_volume_up(self) -> None:
        """Set volume up."""
        return await self._volume_control.set_volume(self._volume + 1)

    async def async_volume_down(self) -> None:
        """Set volume down."""
        return await self._volume_control.set_volume(self._volume - 1)

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        try:
            await self.coordinator.device.set_power(True)
        except SongpalException as ex:
            if ex.code == ERROR_REQUEST_RETRY:
                _LOGGER.debug(
                    "Swallowing %s, the device might be already in the wanted state", ex
                )
                return
            raise

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        try:
            await self.coordinator.device.set_power(False)
        except SongpalException as ex:
            if ex.code == ERROR_REQUEST_RETRY:
                _LOGGER.debug(
                    "Swallowing %s, the device might be already in the wanted state", ex
                )
                return
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s", mute)
        return await self._volume_control.set_mute(mute)
