"""Media player platform for LG IR integration."""

from __future__ import annotations

import logging

from infrared_protocols.codes.lg.tv import LGTVCode, make_command as make_lg_tv_command

from homeassistant.components.infrared import async_send_command
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, DOMAIN, LGDeviceType

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR media player from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type == LGDeviceType.TV:
        async_add_entities([LgIrTvMediaPlayer(entry, infrared_entity_id)])


class LgIrTvMediaPlayer(MediaPlayerEntity):
    """LG IR media player entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize LG IR media player."""
        self._infrared_entity_id = infrared_entity_id
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_state = MediaPlayerState.ON
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="LG TV", manufacturer="LG"
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared entity state changes."""
        await super().async_added_to_hass()

        @callback
        def _async_ir_state_changed(event: Event[EventStateChangedData]) -> None:
            """Handle infrared entity state changes."""
            new_state = event.data["new_state"]
            ir_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            if ir_available != self.available:
                _LOGGER.info(
                    "Infrared entity %s for media player %s is %s",
                    self._infrared_entity_id,
                    self.entity_id,
                    "available" if ir_available else "unavailable",
                )

                self._attr_available = ir_available
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._infrared_entity_id], _async_ir_state_changed
            )
        )

        # Set initial availability based on current infrared entity state
        ir_state = self.hass.states.get(self._infrared_entity_id)
        self._attr_available = (
            ir_state is not None and ir_state.state != STATE_UNAVAILABLE
        )

    async def _send_command(self, code: LGTVCode) -> None:
        """Send an IR command using the LG protocol."""
        await async_send_command(
            self.hass,
            self._infrared_entity_id,
            make_lg_tv_command(code),
            context=self._context,
        )

    async def async_turn_on(self) -> None:
        """Turn on the TV."""
        await self._send_command(LGTVCode.POWER)

    async def async_turn_off(self) -> None:
        """Turn off the TV."""
        await self._send_command(LGTVCode.POWER)

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_command(LGTVCode.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_command(LGTVCode.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_command(LGTVCode.MUTE)

    async def async_media_next_track(self) -> None:
        """Send channel up command."""
        await self._send_command(LGTVCode.CHANNEL_UP)

    async def async_media_previous_track(self) -> None:
        """Send channel down command."""
        await self._send_command(LGTVCode.CHANNEL_DOWN)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_command(LGTVCode.PLAY)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_command(LGTVCode.PAUSE)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_command(LGTVCode.STOP)
