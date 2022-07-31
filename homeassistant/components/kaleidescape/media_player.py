"""Kaleidescape Media Player."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kaleidescape import const as kaleidescape_const

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.util.dt import utcnow

from .const import DOMAIN as KALEIDESCAPE_DOMAIN
from .entity import KaleidescapeEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


KALEIDESCAPE_PLAYING_STATES = [
    kaleidescape_const.PLAY_STATUS_PLAYING,
    kaleidescape_const.PLAY_STATUS_FORWARD,
    kaleidescape_const.PLAY_STATUS_REVERSE,
]

KALEIDESCAPE_PAUSED_STATES = [kaleidescape_const.PLAY_STATUS_PAUSED]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform from a config entry."""
    entities = [KaleidescapeMediaPlayer(hass.data[KALEIDESCAPE_DOMAIN][entry.entry_id])]
    async_add_entities(entities)


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
    def state(self) -> str:
        """State of device."""
        if self._device.power.state == kaleidescape_const.DEVICE_POWER_STATE_STANDBY:
            return STATE_OFF
        if self._device.movie.play_status in KALEIDESCAPE_PLAYING_STATES:
            return STATE_PLAYING
        if self._device.movie.play_status in KALEIDESCAPE_PAUSED_STATES:
            return STATE_PAUSED
        return STATE_IDLE

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
