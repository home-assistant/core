"""Support for System Bridge media player."""
from __future__ import annotations

from systembridge import Bridge

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge media player based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    async_add_entities([BridgeMediaPlayer(coordinator, bridge)])


class BridgeMediaPlayer(BridgeDeviceEntity, MediaPlayerEntity):
    """Defines a System Bridge media player."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge) -> None:
        """Initialize System Bridge media player."""
        super().__init__(coordinator, bridge, "media_player", None, None, True)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            SUPPORT_PAUSE
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_PLAY
            | SUPPORT_TURN_OFF
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
        )
