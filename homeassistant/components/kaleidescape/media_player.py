"""Kaleidescape Media Player."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from kaleidescape import const as kaleidescape_const

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_COMMAND, CONF_PARAMS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from . import KaleidescapeConfigEntry
from .const import (
    EVENT_TYPE_USER_DEFINED_EVENT,
    EVENT_TYPE_VOLUME_DOWN,
    EVENT_TYPE_VOLUME_MUTE,
    EVENT_TYPE_VOLUME_QUERY,
    EVENT_TYPE_VOLUME_SET,
    EVENT_TYPE_VOLUME_UP,
)
from .entity import KaleidescapeEntity

if TYPE_CHECKING:
    from kaleidescape import Device as KaleidescapeDevice

KALEIDESCAPE_PLAYING_STATES = [
    kaleidescape_const.PLAY_STATUS_PLAYING,
    kaleidescape_const.PLAY_STATUS_FORWARD,
    kaleidescape_const.PLAY_STATUS_REVERSE,
]

KALEIDESCAPE_PAUSED_STATES = [kaleidescape_const.PLAY_STATUS_PAUSED]

DEBOUNCE_TIME = 0.5

_LOGGER = logging.getLogger(__name__)

EVENT_DATA_VOLUME_LEVEL = "volume_level"

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
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )
    _attr_name = None

    def __init__(self, device: KaleidescapeDevice) -> None:
        """Initialize the Kaleidescape media player entity."""
        super().__init__(device)
        self._volume_capabilities: int = kaleidescape_const.VOLUME_CAPABILITIES_NONE
        self._debounce_set_volume: asyncio.TimerHandle | None = None

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if self._debounce_set_volume is not None:
            self._debounce_set_volume.cancel()
            self._debounce_set_volume = None

    async def _async_handle_device_event(
        self, event: str, params: list[str] | None = None
    ) -> None:
        """Handle USER_DEFINED_EVENT related device events."""
        if event != kaleidescape_const.USER_DEFINED_EVENT:
            return

        if not params or not isinstance(params, list):
            _LOGGER.warning(
                "Received USER_DEFINED_EVENT %s with invalid params: %s",
                event,
                params,
            )
            return

        command = params[0]
        fields = params[1:] if len(params) > 1 else []

        _LOGGER.debug(
            "Received USER_DEFINED_EVENT command=%s fields=%s", command, fields
        )

        match command:
            case kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY:
                await self._async_handle_volume_query()
            case c if c in KALEIDESCAPE_EVENTS_VOLUME_UP:
                self._handle_volume_up_pressed()
            case c if c in KALEIDESCAPE_EVENTS_VOLUME_DOWN:
                self._handle_volume_down_pressed()
            case kaleidescape_const.USER_DEFINED_EVENT_TOGGLE_MUTE:
                self._handle_volume_mute_pressed()
            case kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL:
                self._handle_set_volume_level(fields)
            case _ if command not in kaleidescape_const.VOLUME_EVENTS:
                self._handle_user_defined_event(command, fields)

    async def _async_handle_volume_query(self) -> None:
        """Handle volume capabilities query from Kaleidescape app."""
        capabilities = self._volume_capabilities or BASELINE_CAPABILITIES
        await self._async_add_volume_capabilities(capabilities, True)
        self._fire_hass_bus_event(EVENT_TYPE_VOLUME_QUERY, {})

    @callback
    def _handle_volume_up_pressed(self) -> None:
        """Handle volume up button pressed."""
        self._fire_hass_bus_event(EVENT_TYPE_VOLUME_UP, {})

    @callback
    def _handle_volume_down_pressed(self) -> None:
        """Handle volume down button pressed."""
        self._fire_hass_bus_event(EVENT_TYPE_VOLUME_DOWN, {})

    @callback
    def _handle_volume_mute_pressed(self) -> None:
        """Handle mute button pressed."""
        self._fire_hass_bus_event(EVENT_TYPE_VOLUME_MUTE, {})

    @callback
    def _handle_set_volume_level(self, fields: list[str]) -> None:
        """Handle volume level set request from Kaleidescape app."""
        try:
            volume_level = int(fields[0])
        except (IndexError, ValueError, TypeError):
            _LOGGER.warning("Invalid level for SET_VOLUME_LEVEL: %s", fields)
            return

        scaled_volume_level = float(max(0, min(100, volume_level)) / 100)
        self._schedule_debounced_set_volume_event(scaled_volume_level)

    @callback
    def _handle_user_defined_event(self, command: str, fields: list[str]) -> None:
        """Handle user defined events."""
        self._fire_hass_bus_event(
            EVENT_TYPE_USER_DEFINED_EVENT,
            {CONF_COMMAND: command, CONF_PARAMS: fields},
        )

    @callback
    def _schedule_debounced_set_volume_event(self, volume_level: float) -> None:
        """Schedule debounced set volume event."""
        if self._debounce_set_volume is not None:
            self._debounce_set_volume.cancel()
            self._debounce_set_volume = None

        def _fire() -> None:
            self._debounce_set_volume = None
            self._fire_hass_bus_event(
                EVENT_TYPE_VOLUME_SET, {EVENT_DATA_VOLUME_LEVEL: volume_level}
            )

        self._debounce_set_volume = self.hass.loop.call_later(DEBOUNCE_TIME, _fire)

    async def async_set_volume_level(self, volume: float) -> None:
        """Service call handler to send volume level back to Kaleidescape app."""
        scaled_level = int(max(0, min(100, round(volume, 3) * 100)))

        await self._async_add_volume_capabilities(
            kaleidescape_const.VOLUME_CAPABILITIES_SET_VOLUME
            | kaleidescape_const.VOLUME_CAPABILITIES_VOLUME_FEEDBACK
        )

        _LOGGER.debug("Sending volume_level=%s to device", scaled_level)

        await self._device.set_volume_level(scaled_level)

    async def async_mute_volume(self, mute: bool) -> None:
        """Service call handler to send mute state back to Kaleidescape app."""
        await self._async_add_volume_capabilities(
            kaleidescape_const.VOLUME_CAPABILITIES_MUTE_CONTROL
            | kaleidescape_const.VOLUME_CAPABILITIES_MUTE_FEEDBACK
        )

        _LOGGER.debug("Sending volume_muted=%s to device", mute)

        await self._device.set_volume_muted(mute)

    async def _async_add_volume_capabilities(
        self, value: int, force: bool = False
    ) -> None:
        """Add volume capabilities to device."""
        new_value = self._volume_capabilities | value
        if new_value == self._volume_capabilities and not force:
            return

        _LOGGER.debug(
            "Changing volume capabilities from %s to %s",
            self._volume_capabilities,
            new_value,
        )

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
