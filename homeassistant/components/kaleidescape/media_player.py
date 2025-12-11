"""Kaleidescape Media Player."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from kaleidescape import const as kaleidescape_const
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_ACTION, CONF_PARAMS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from . import KaleidescapeConfigEntry
from .const import (
    EVENT_TYPE_USER_DEFINED_EVENT,
    EVENT_TYPE_VOLUME_DOWN_PRESSED,
    EVENT_TYPE_VOLUME_MUTE_PRESSED,
    EVENT_TYPE_VOLUME_SET_UPDATED,
    EVENT_TYPE_VOLUME_UP_PRESSED,
    SERVICE_ATTR_VOLUME_LEVEL,
    SERVICE_ATTR_VOLUME_MUTED,
    SERVICE_SEND_VOLUME_LEVEL,
    SERVICE_SEND_VOLUME_MUTED,
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

EVENT_DATA_VOLUME_LEVEL = "level"

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

    platform.async_register_entity_service(
        SERVICE_SEND_VOLUME_LEVEL,
        {
            vol.Required(SERVICE_ATTR_VOLUME_LEVEL): vol.All(
                vol.Coerce(float),
                vol.Range(min=0.0, max=1.0),
            )
        },
        "async_send_volume_level",
    )

    platform.async_register_entity_service(
        SERVICE_SEND_VOLUME_MUTED,
        {vol.Required(SERVICE_ATTR_VOLUME_MUTED): cv.boolean},
        "async_send_volume_muted",
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
        self._debounce_set_volume: asyncio.TimerHandle | None = None

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if self._debounce_set_volume is not None:
            self._debounce_set_volume.cancel()
            self._debounce_set_volume = None

    async def async_handle_device_event(
        self, event: str, params: list[str] | None = None
    ) -> None:
        """Handle USER_DEFINED_EVENT related device events."""
        if event != kaleidescape_const.USER_DEFINED_EVENT:
            return

        if not isinstance(params, list) or len(params) == 0:
            _LOGGER.warning(
                "Received USER_DEFINED_EVENT %s with invalid params: %s",
                event,
                params,
            )
            return

        command = params[0]
        fields = params[1] if len(params) > 1 else None

        _LOGGER.debug(
            "Received USER_DEFINED_EVENT command=%s fields=%s", command, fields
        )

        if command == kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY:
            # A Kaleidescape app is requesting volume capabilities.
            capabilities = (
                self._volume_capabilities
                if self._volume_capabilities
                else BASELINE_CAPABILITIES
            )
            await self._async_add_volume_capabilities(capabilities, True)

        elif command in KALEIDESCAPE_EVENTS_VOLUME_UP:
            # A Kaleidescape remote or app volume up button pressed. Inform automations.
            self._fire_hass_bus_event(EVENT_TYPE_VOLUME_UP_PRESSED, {})

        elif command in KALEIDESCAPE_EVENTS_VOLUME_DOWN:
            # A Kaleidescape remote or app volume down button pressed. Inform automations.
            self._fire_hass_bus_event(EVENT_TYPE_VOLUME_DOWN_PRESSED, {})

        elif command == kaleidescape_const.USER_DEFINED_EVENT_TOGGLE_MUTE:
            # A Kaleidescape remote or app mute button pressed. Inform automations.
            self._fire_hass_bus_event(EVENT_TYPE_VOLUME_MUTE_PRESSED, {})

        elif command == kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL:
            # A Kaleidescape app volume slider changed. Debounce rapid changes and inform automations.
            try:
                level = float(max(0, min(100, int(fields or 0))) / 100)
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid SET_VOLUME_LEVEL value: %s", fields)
                return

            self._schedule_debounced_set_volume_event(level)

        elif command not in kaleidescape_const.VOLUME_EVENTS:
            # Fire all non-volume events generically for custom automations
            self._fire_hass_bus_event(
                EVENT_TYPE_USER_DEFINED_EVENT,
                {CONF_ACTION: command, CONF_PARAMS: fields},
            )

    @callback
    def _fire_hass_bus_event(self, event_type: str, event_data: dict) -> None:
        """Fire volume bus event."""
        _LOGGER.debug("Firing bus event %s %s", event_type, event_data)
        self.hass.bus.async_fire(event_type, event_data)

    @callback
    def _schedule_debounced_set_volume_event(self, level: float) -> None:
        """Schedule debounced set volume event."""
        if self._debounce_set_volume is not None:
            self._debounce_set_volume.cancel()
            self._debounce_set_volume = None

        def _fire() -> None:
            self._debounce_set_volume = None
            self._fire_hass_bus_event(
                EVENT_TYPE_VOLUME_SET_UPDATED, {EVENT_DATA_VOLUME_LEVEL: level}
            )

        self._debounce_set_volume = self.hass.loop.call_later(DEBOUNCE_TIME, _fire)

    async def async_send_volume_level(self, level: float) -> None:
        """Service call handler to send volume level back to Kaleidescape app."""
        new_level = int(max(0, min(100, round(level * 100))))

        await self._async_add_volume_capabilities(
            kaleidescape_const.VOLUME_CAPABILITIES_SET_VOLUME
            | kaleidescape_const.VOLUME_CAPABILITIES_VOLUME_FEEDBACK
        )

        _LOGGER.debug("Sending volume_level=%s to device", new_level)

        await self._device.set_volume_level(new_level)

    async def async_send_volume_muted(self, muted: bool) -> None:
        """Service call handler to send mute state back to Kaleidescape app."""
        await self._async_add_volume_capabilities(
            kaleidescape_const.VOLUME_CAPABILITIES_MUTE_CONTROL
            | kaleidescape_const.VOLUME_CAPABILITIES_MUTE_FEEDBACK
        )

        _LOGGER.debug("Sending volume_muted=%s to device", bool(muted))

        await self._device.set_volume_muted(muted)

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
