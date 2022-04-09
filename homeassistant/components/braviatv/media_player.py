"""Support for interface with a Bravia TV."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BraviaTVCoordinator
from .const import ATTR_MANUFACTURER, DEFAULT_NAME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bravia TV Media Player from a config_entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    unique_id = config_entry.unique_id
    assert unique_id is not None
    device_info = DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer=ATTR_MANUFACTURER,
        model=config_entry.title,
        name=DEFAULT_NAME,
    )

    async_add_entities(
        [BraviaTVMediaPlayer(coordinator, DEFAULT_NAME, unique_id, device_info)]
    )


class BraviaTVMediaPlayer(CoordinatorEntity[BraviaTVCoordinator], MediaPlayerEntity):
    """Representation of a Bravia TV Media Player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(
        self,
        coordinator: BraviaTVCoordinator,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""

        self._attr_device_info = device_info
        self._attr_name = name
        self._attr_unique_id = unique_id

        super().__init__(coordinator)

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.coordinator.is_on:
            return STATE_PLAYING if self.coordinator.playing else STATE_PAUSED
        return STATE_OFF

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.coordinator.source

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return self.coordinator.source_list

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.coordinator.volume_level

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self.coordinator.muted

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.coordinator.media_title

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self.coordinator.channel_name

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.coordinator.duration

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self.coordinator.async_turn_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.async_set_volume_level(volume)

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self.coordinator.async_volume_up()

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self.coordinator.async_volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self.coordinator.async_volume_mute(mute)

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        await self.coordinator.async_select_source(source)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.async_media_play()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.async_media_pause()

    async def async_media_stop(self) -> None:
        """Send media stop command to media player."""
        await self.coordinator.async_media_stop()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.async_media_next_track()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.async_media_previous_track()
