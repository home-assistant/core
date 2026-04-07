"""Event platform for LG IR integration."""

from __future__ import annotations

import logging

from infrared_protocols.codes.lg.tv import LGTVCode

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_RECEIVER_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity
from .nec_decoder import from_raw_timings

_LOGGER = logging.getLogger(__name__)

# LG TV NEC address (extended NEC, 16-bit)
_LG_TV_NEC_ADDRESS = 0xFB04

# Build a lookup from command byte value -> lowercase LGTVCode name
_COMMAND_BYTE_TO_EVENT_TYPE: dict[int, str] = {
    code.value: code.name.lower() for code in LGTVCode
}

# Event type for commands from the LG TV address that don't match any known code
_EVENT_TYPE_UNKNOWN = "unknown"

# All possible event types: known LG TV codes + unknown
_EVENT_TYPES: list[str] = [code.name.lower() for code in LGTVCode] + [
    _EVENT_TYPE_UNKNOWN
]

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR event entity from config entry."""
    receiver_entity_id = entry.data[CONF_INFRARED_RECEIVER_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]

    if device_type == LGDeviceType.TV:
        async_add_entities(
            [
                LgIrReceivedCommandEvent(
                    entry,
                    receiver_entity_id,
                )
            ]
        )


class LgIrReceivedCommandEvent(LgIrEntity, EventEntity):
    """Event entity that fires when an LG TV IR command is received."""

    _attr_translation_key = "received_command"
    _attr_event_types = _EVENT_TYPES

    def __init__(
        self,
        entry: ConfigEntry,
        receiver_entity_id: str,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(entry, receiver_entity_id, unique_id_suffix="received_command")

    async def async_added_to_hass(self) -> None:
        """Subscribe to the IR receiver when added to hass."""
        await super().async_added_to_hass()

        @callback
        def _handle_signal(signal: InfraredReceivedSignal) -> None:
            """Handle a received IR signal."""
            nec_command = from_raw_timings(signal.timings)
            if nec_command is None:
                return

            if nec_command.address != _LG_TV_NEC_ADDRESS:
                return

            event_type = _COMMAND_BYTE_TO_EVENT_TYPE.get(
                nec_command.command, _EVENT_TYPE_UNKNOWN
            )

            _LOGGER.debug(
                "Received LG TV IR command: %s (0x%02X)",
                event_type,
                nec_command.command,
            )

            self._trigger_event(event_type)
            self.async_write_ha_state()

        @callback
        def _async_subscribe_when_available() -> None:
            """Subscribe to the IR receiver when it becomes available."""
            ir_state = self.hass.states.get(self._infrared_entity_id)
            self._attr_available = (
                ir_state is not None and ir_state.state != STATE_UNAVAILABLE
            )
            if not self._attr_available:
                return
            _LOGGER.info(
                "Subscribing to infrared receiver entity %s for %s",
                self._infrared_entity_id,
                self.entity_id,
            )
            # TODO: unsubscribe before resubscribing if already subscribed
            self.async_on_remove(
                async_subscribe_receiver(
                    self.hass, self._infrared_entity_id, _handle_signal
                )
            )

        @callback
        def _async_ir_state_changed(event: Event[EventStateChangedData]) -> None:
            """Handle infrared entity state changes."""
            _async_subscribe_when_available()

        _async_subscribe_when_available()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._infrared_entity_id], _async_ir_state_changed
            )
        )
