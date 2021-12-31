"""Support for Songpal-enabled (Sony) media devices."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDeviceClass, MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    SET_SOUND_SETTING,
    TITLE_TEXTID_REPEAT_TYPE,
    TITLE_TEXTID_SHUFFLE_TYPE,
    TITLE_TEXTID_SOUND_MODE,
)
from .coordinator import SongpalCoordinator
from .entity import SongpalEntity

_LOGGER = logging.getLogger(__name__)

PARAM_NAME = "name"
PARAM_VALUE = "value"

PLAYING_STATES_MAP = {
    "PLAYING": STATE_PLAYING,
    "STOPPED": STATE_IDLE,
    "PAUSED": STATE_PAUSED,
}

# TitleTextIDs of settings that are used directly by the MediaPlayerEntity instead of
# being exposed as separate entities!
MEDIA_PLAYER_SETTINGS = {
    TITLE_TEXTID_REPEAT_TYPE,
    TITLE_TEXTID_SHUFFLE_TYPE,
    TITLE_TEXTID_SOUND_MODE,
}

DEVICE_CLASS_MAP = {
    "tv": MediaPlayerDeviceClass.TV,
    "internetTV": MediaPlayerDeviceClass.TV,
    "homeTheaterSystem": MediaPlayerDeviceClass.RECEIVER,
    "personalAudio": MediaPlayerDeviceClass.SPEAKER,
}

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up from legacy configuration file. Obsolete."""
    _LOGGER.error(
        "Configuring Songpal through media_player platform is no longer supported. Convert to songpal platform or UI configuration"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up songpal media player."""
    name = config_entry.data[CONF_NAME]
    coordinator: SongpalCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    songpal_entity = SongpalMediaPlayerEntity(name, coordinator)
    async_add_entities([songpal_entity], True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SET_SOUND_SETTING,
        {vol.Required(PARAM_NAME): cv.string, vol.Required(PARAM_VALUE): cv.string},
        "async_set_sound_setting",
    )


class SongpalMediaPlayerEntity(MediaPlayerEntity, SongpalEntity):
    """Class representing a Songpal device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )

    def __init__(self, name, coordinator: SongpalCoordinator):
        """Init."""
        super().__init__(coordinator)

        self._attr_name = name
        self._attr_unique_id = self.coordinator.data.unique_id
        self._attr_device_class = DEVICE_CLASS_MAP.get(
            self.coordinator.data.interface_info.productCategory, None
        )

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        _LOGGER.debug("Calling set_sound_setting with %s: %s", name, value)
        await self.coordinator.device.set_sound_settings(name, value)

    @property
    def state(self) -> str | None:
        """Return the current state of the media player."""
        if not self.coordinator.data.power:
            return STATE_OFF

        if not self.coordinator.data.playing_content.stateInfo:
            return STATE_IDLE

        reported_state = self.coordinator.data.playing_content.stateInfo.state
        if reported_state not in PLAYING_STATES_MAP:
            _LOGGER.warning("[%s] Unknown reported state %s", self.name, reported_state)
            return None

        return PLAYING_STATES_MAP[reported_state]

    @property
    def source_list(self) -> list[str]:
        """Return the title of available sources."""
        return [
            source.title for source in self.coordinator.data.inputs if source.active
        ]

    @property
    def source(self):
        """Return currently active source."""
        for source in self.coordinator.data.inputs:
            if source.uri == self.coordinator.data.playing_content.source:
                return source.title

        return None

    @property
    def sound_mode_list(self) -> list[str]:
        """Return the list of available sound modes."""
        sound_field_setting = self.coordinator.data.settings[TITLE_TEXTID_SOUND_MODE]
        return [
            candidate.title
            for candidate in sound_field_setting.candidate
            if candidate.isAvailable
        ]

    @property
    def sound_mode(self) -> str | None:
        """Return the currently selected sound mode."""
        sound_field_setting = self.coordinator.data.settings[TITLE_TEXTID_SOUND_MODE]

        for candidate in sound_field_setting.candidate:
            if candidate.value == sound_field_setting.currentValue:
                return candidate.title
        return None

    @property
    def volume_level(self):
        """Return volume level."""
        volume = (
            self.coordinator.data.volume.volume / self.coordinator.data.volume.maxVolume
        )
        return volume

    @property
    def is_volume_muted(self) -> bool:
        """Return whether the volume is currently muted."""
        return self.coordinator.data.volume.is_muted

    async def async_set_volume_level(self, volume):
        """Set volume level."""
        volume = int(volume * self.coordinator.data.volume.maxVolume)
        _LOGGER.debug("Setting volume to %s", volume)
        return await self.coordinator.data.volume.set_volume(volume)

    async def async_volume_up(self):
        """Set volume up."""
        return await self.coordinator.data.volume.set_volume(
            self.coordinator.data.volume.volume + 1
        )

    async def async_volume_down(self):
        """Set volume down."""
        return await self.coordinator.data.volume.set_volume(
            self.coordinator.data.volume.volume - 1
        )

    async def async_mute_volume(self, mute):
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s", mute)
        return await self.coordinator.data.volume.set_mute(mute)

    async def async_turn_on(self):
        """Turn the device on."""
        return await self.coordinator.device.set_power(True)

    async def async_turn_off(self):
        """Turn the device off."""
        return await self.coordinator.device.set_power(False)

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        for out in self.coordinator.data.inputs:
            if out.title == source:
                await out.activate()
                return

        _LOGGER.error("Unable to find output: %s", source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Change the selected sound mode."""
        sound_field_setting = self.coordinator.data.settings[TITLE_TEXTID_SOUND_MODE]
        for candidate in sound_field_setting.candidate:
            if candidate.title == sound_mode:
                await self.coordinator.device.set_soundfield(candidate.value)
