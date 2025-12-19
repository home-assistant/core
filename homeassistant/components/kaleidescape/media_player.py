"""Kaleidescape Media Player."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from kaleidescape import const as kaleidescape_const
import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import SERVICE_VOLUME_MUTE, SERVICE_VOLUME_SET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from . import KaleidescapeConfigEntry
from .entity import KaleidescapeEntity

if TYPE_CHECKING:
    from kaleidescape import Device as KaleidescapeDevice

KALEIDESCAPE_PLAYING_STATES = [
    kaleidescape_const.PLAY_STATUS_PLAYING,
    kaleidescape_const.PLAY_STATUS_FORWARD,
    kaleidescape_const.PLAY_STATUS_REVERSE,
]

KALEIDESCAPE_PAUSED_STATES = [kaleidescape_const.PLAY_STATUS_PAUSED]

_LOGGER = logging.getLogger(__name__)


ATTR_VOLUME_CAPABILITIES = "volume_capabilities"

BASELINE_CAPABILITIES = (
    kaleidescape_const.VOLUME_CAPABILITIES_VOLUME_CONTROL
    | kaleidescape_const.VOLUME_CAPABILITIES_MUTE_CONTROL
)

KALEIDESCAPE_EVENTS_VOLUME_UP = (
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_UP,
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_UP_PRESS,
)

KALEIDESCAPE_EVENTS_VOLUME_DOWN = (
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_DOWN,
    kaleidescape_const.USER_DEFINED_EVENT_VOLUME_DOWN_PRESS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KaleidescapeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    async_add_entities([KaleidescapeMediaPlayer(entry.runtime_data)])

    platform = entity_platform.async_get_current_platform()

    # Note: Kaleidescape devices don't directly manage volume state, instead they just pass volume events.
    # This integration simply acts as a bridge for user automations to sync volume state with other volume
    # capable integrations.

    platform.async_register_entity_service(
        SERVICE_VOLUME_SET,
        vol.All(
            cv.make_entity_service_schema(
                {vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float}
            ),
            lambda v: (v.update({"volume": v.pop(ATTR_MEDIA_VOLUME_LEVEL)}) or v),
        ),
        "async_set_volume_level",
    )

    platform.async_register_entity_service(
        SERVICE_VOLUME_MUTE,
        vol.All(
            cv.make_entity_service_schema(
                {vol.Required(ATTR_MEDIA_VOLUME_MUTED): cv.boolean}
            ),
            lambda v: (v.update({"mute": v.pop(ATTR_MEDIA_VOLUME_MUTED)}) or v),
        ),
        "async_mute_volume",
    )


class KaleidescapeMediaPlayer(KaleidescapeEntity, MediaPlayerEntity):
    """Representation of a Kaleidescape device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )
    _attr_name = None

    def __init__(self, device: KaleidescapeDevice) -> None:
        """Initialize the Kaleidescape media player entity."""
        super().__init__(device)
        self._volume_capabilities: int = kaleidescape_const.VOLUME_CAPABILITIES_NONE

    async def _async_handle_event(self, event: str, *args: Any) -> None:
        """Handle user defined device events."""
        if event != kaleidescape_const.USER_DEFINED_EVENT:
            return

        if not args or not isinstance(args[0], list) or not args[0]:
            return

        command = args[0][0]

        if command == kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY:
            capabilities = self._volume_capabilities or BASELINE_CAPABILITIES
            await self._async_update_volume_capabilities(capabilities, True)

    async def async_set_volume_level(self, volume: float) -> None:
        """Service call handler to send volume level back to any listening Kaleidescape mobile app."""
        await self._async_update_volume_capabilities(
            kaleidescape_const.VOLUME_CAPABILITIES_SET_VOLUME
            | kaleidescape_const.VOLUME_CAPABILITIES_VOLUME_FEEDBACK
        )

        scaled_level = int(max(0, min(100, round(volume, 3) * 100)))

        _LOGGER.debug("Sending volume level=%s feedback to device", scaled_level)

        await self._device.set_volume_level(scaled_level)

    async def async_mute_volume(self, mute: bool) -> None:
        """Service call handler to send mute state back to any listening Kaleidescape mobile app."""
        await self._async_update_volume_capabilities(
            kaleidescape_const.VOLUME_CAPABILITIES_MUTE_CONTROL
            | kaleidescape_const.VOLUME_CAPABILITIES_MUTE_FEEDBACK
        )

        _LOGGER.debug("Sending volume muted=%s feedback to device", mute)

        await self._device.set_volume_muted(mute)

    async def _async_update_volume_capabilities(
        self, value: int, force: bool = False
    ) -> None:
        """Send updated volume capabilities to any listening Kaleidescape mobile app."""
        if not self._volume_capabilities:
            self._volume_capabilities = BASELINE_CAPABILITIES

        new_value = self._volume_capabilities | value
        if new_value == self._volume_capabilities and not force:
            return

        _LOGGER.debug("Updating volume capabilities to %s", new_value)

        self._volume_capabilities = new_value
        await self._device.set_volume_capabilities(new_value)

        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Send leave standby command."""
        await self._device.leave_standby()

    async def async_turn_off(self) -> None:
        """Send enter standby command."""
        await self._device.enter_standby()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._device.pause()

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._device.play()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._device.stop()

    async def async_media_next_track(self) -> None:
        """Send track next command."""
        await self._device.next()

    async def async_media_previous_track(self) -> None:
        """Send track previous command."""
        await self._device.previous()

    @property
    def state(self) -> MediaPlayerState:
        """State of device."""
        if self._device.power.state == kaleidescape_const.DEVICE_POWER_STATE_STANDBY:
            return MediaPlayerState.OFF
        if self._device.movie.play_status in KALEIDESCAPE_PLAYING_STATES:
            return MediaPlayerState.PLAYING
        if self._device.movie.play_status in KALEIDESCAPE_PAUSED_STATES:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self._device.is_connected

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        if self._device.movie.handle:
            return self._device.movie.handle
        return None

    @property
    def media_content_type(self) -> str | None:
        """Content type of current playing media."""
        return self._device.movie.media_type

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if self._device.movie.title_length:
            return self._device.movie.title_length
        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self._device.movie.title_location:
            return self._device.movie.title_location
        return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        if self._device.movie.play_status in KALEIDESCAPE_PLAYING_STATES:
            return utcnow()
        return None

    @property
    def media_image_url(self) -> str:
        """Image url of current playing media."""
        return self._device.movie.cover

    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        return self._device.movie.title

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {ATTR_VOLUME_CAPABILITIES: self._volume_capabilities}
