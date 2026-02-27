"""Media player for Trinnov Altitude integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import TrinnovAltitudeEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the media player platform from a config entry."""
    async_add_entities([TrinnovAltitudeMediaPlayer(hass.data[DOMAIN][entry.entry_id])])


class TrinnovAltitudeMediaPlayer(TrinnovAltitudeEntity, MediaPlayerEntity):
    """Representation of a Trinnov Altitude device."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute volume."""
        await self._device.mute_set(mute)

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        try:
            await self._device.source_set_by_name(source)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def async_turn_on(self) -> None:
        """Power on."""
        self._device.power_on()

    async def async_turn_off(self) -> None:
        """Power off."""
        await self._device.power_off()

    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._device.volume_up()

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._device.volume_down()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        await self._device.volume_percentage_set(volume * 100.0)

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self._device.power_on_available() or self._device.connected

    @property
    def input_source(self) -> str | None:
        """Current source."""
        return self._device.state.source

    @property
    def input_source_list(self) -> list[str] | None:
        """Available source list."""
        return list(self._device.state.sources.values())

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._device.state.mute

    @property
    def state(self) -> MediaPlayerState:
        """State of device."""
        if not self._device.connected or not self._device.state.synced:
            return MediaPlayerState.OFF
        if self._device.state.source_format:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Volume level (0..1)."""
        percentage = self._device.volume_percentage
        if percentage is None:
            return None
        return percentage / 100.0
