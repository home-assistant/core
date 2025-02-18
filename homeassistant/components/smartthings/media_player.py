"""Support for media players through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import APIResponseError, Capability, DeviceEntity

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

VALUE_TO_STATE = {
    "buffering": MediaPlayerState.BUFFERING,
    "pause": MediaPlayerState.PAUSED,
    "paused": MediaPlayerState.PAUSED,
    "play": MediaPlayerState.PLAYING,
    "playing": MediaPlayerState.PLAYING,
    "stop": MediaPlayerState.IDLE,
    "stopped": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add media players for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        SmartThingsMediaPlayer(device)
        for device in broker.devices.values()
        if broker.any_assigned(device.device_id, MEDIA_PLAYER_DOMAIN)
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        Capability.audio_mute,
        Capability.audio_volume,
        Capability.media_input_source,
        Capability.media_playback,
        Capability.switch,
    ]
    # Must have one of these.
    media_player_capabilities = [
        Capability.audio_mute,
        Capability.audio_volume,
        Capability.media_input_source,
        Capability.media_playback,
    ]
    if any(capability in capabilities for capability in media_player_capabilities):
        return supported
    return None


class SmartThingsMediaPlayer(SmartThingsEntity, MediaPlayerEntity):
    """Define a SmartThings media player."""

    def __init__(self, device: DeviceEntity) -> None:
        """Initialize the media_player class."""
        super().__init__(device)
        if Capability.audio_mute in device.capabilities:
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if Capability.audio_volume in device.capabilities:
            self._attr_supported_features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if Capability.media_input_source in device.capabilities:
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if Capability.media_playback in device.capabilities:
            self._attr_supported_features |= (
                MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
            )
        if Capability.switch in device.capabilities:
            self._attr_supported_features |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the media player on."""
        try:
            await self._device.switch_on(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"err": str(err)},
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the media player off."""
        try:
            await self._device.switch_off(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError("Failed to turn off SmartThings device") from err

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute volume."""
        if mute:
            try:
                await self._device.mute(set_status=True)
                self.async_write_ha_state()
            except APIResponseError as err:
                raise HomeAssistantError(
                    "Failed to mute volume on SmartThings device"
                ) from err
        else:
            try:
                await self._device.unmute(set_status=True)
                self.async_write_ha_state()
            except APIResponseError as err:
                raise HomeAssistantError(
                    "Failed to unmute volume on SmartThings device"
                ) from err

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        try:
            await self._device.set_volume(int(volume * 100), set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to set volume on SmartThings device"
            ) from err

    async def async_volume_up(self) -> None:
        """Increase volume."""
        try:
            await self._device.volume_up(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to increase volume on SmartThings device"
            ) from err

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        try:
            await self._device.volume_down(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to decrease volume on SmartThings device"
            ) from err

    async def async_media_play(self) -> None:
        """Play media."""
        try:
            await self._device.play(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to play media on SmartThings device"
            ) from err

    async def async_media_pause(self) -> None:
        """Pause media."""
        try:
            await self._device.pause(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to pause media on SmartThings device"
            ) from err

    async def async_media_stop(self) -> None:
        """Stop media."""
        try:
            await self._device.stop(set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to stop media on SmartThings device"
            ) from err

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        try:
            await self._device.set_input_source(source, set_status=True)
            self.async_write_ha_state()
        except APIResponseError as err:
            raise HomeAssistantError(
                "Failed to set source on SmartThings device"
            ) from err

    @property
    def media_title(self) -> str | None:
        """Title of the current media."""
        return self._device.status.media_title

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the media player."""
        if not self._device.status.switch:
            return MediaPlayerState.OFF
        if self._device.status.playback_status in VALUE_TO_STATE:
            return VALUE_TO_STATE[self._device.status.playback_status]
        return MediaPlayerState.ON

    @property
    def is_volume_muted(self) -> bool | None:
        """Returns if the volume is muted."""
        if self.supported_features & MediaPlayerEntityFeature.VOLUME_MUTE:
            return self._device.status.mute
        return None

    @property
    def volume_level(self) -> float | None:
        """Volume level."""
        if self.supported_features & MediaPlayerEntityFeature.VOLUME_SET:
            return self._device.status.volume / 100
        return None

    @property
    def source(self) -> str | None:
        """Input source."""
        if self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
            return self._device.status.input_source
        return None

    @property
    def source_list(self) -> list[str] | None:
        """List of input sources."""
        if self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
            return self._device.status.supported_input_sources
        return None
