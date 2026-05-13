"""Event platform for LG IR integration."""

import logging

from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_RECEIVER_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# TODO: remove this when https://github.com/home-assistant-libs/infrared-protocols/pull/38
# is merged
_LG_TV_NEC_ADDRESS = 0xFB04

_COMMAND_BYTE_TO_EVENT_TYPE: dict[int, str] = {
    0x79: "aspect",
    0x28: "back",
    0x72: "blue",
    0x01: "channel_down",
    0x00: "channel_up",
    0x5B: "exit",
    0xFF: "ez_adjust",
    0x8E: "fast_forward",
    0x63: "green",
    0xA9: "guide",
    0xCE: "hdmi_1",
    0xCC: "hdmi_2",
    0xE9: "hdmi_3",
    0xDA: "hdmi_4",
    0x7C: "home",
    0xAA: "info",
    0x0B: "input",
    0xFB: "in_start",
    0xCA: "list",
    0x43: "menu",
    0x09: "mute",
    0x41: "nav_down",
    0x07: "nav_left",
    0x06: "nav_right",
    0x40: "nav_up",
    0x10: "num_0",
    0x11: "num_1",
    0x12: "num_2",
    0x13: "num_3",
    0x14: "num_4",
    0x15: "num_5",
    0x16: "num_6",
    0x17: "num_7",
    0x18: "num_8",
    0x19: "num_9",
    0x44: "ok",
    0xBA: "pause",
    0xB0: "play",
    0x08: "power",
    0xC4: "power_on",
    0xC5: "power_off",
    0x71: "red",
    0x8F: "rewind",
    0x0A: "sap",
    0x45: "settings",
    0xB1: "stop",
    0x39: "subtitle",
    0x20: "text",
    0x03: "volume_down",
    0x02: "volume_up",
    0x61: "yellow",
}
_EVENT_TYPE_UNKNOWN = "unknown"
_EVENT_TYPES: list[str] = [*_COMMAND_BYTE_TO_EVENT_TYPE.values(), _EVENT_TYPE_UNKNOWN]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR event entity from config entry."""
    if entry.data[CONF_DEVICE_TYPE] != LGDeviceType.TV:
        return
    if not (receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID)):
        return
    async_add_entities([LgIrReceivedCommandEvent(entry, receiver_entity_id)])


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
        self._remove_signal_subscription: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the IR receiver when added to hass."""
        await super().async_added_to_hass()

        self._async_update_receiver_subscription()
        self.async_on_remove(self._async_unsubscribe_receiver)
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._infrared_entity_id],
                self._async_ir_state_changed,
            )
        )

    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""
        nec_command = NECCommand.from_raw_timings(signal.timings)
        if nec_command is None:
            return

        if nec_command.address != _LG_TV_NEC_ADDRESS:
            return

        event_type = _COMMAND_BYTE_TO_EVENT_TYPE.get(
            nec_command.command, _EVENT_TYPE_UNKNOWN
        )

        _LOGGER.debug(
            "Received LG TV IR command: %s (0x%02X)", event_type, nec_command.command
        )

        self._trigger_event(event_type)
        self.async_write_ha_state()

    @callback
    def _async_unsubscribe_receiver(self) -> None:
        """Unsubscribe from the current IR receiver."""
        if self._remove_signal_subscription is None:
            return
        self._remove_signal_subscription()
        self._remove_signal_subscription = None

    @callback
    def _async_update_receiver_subscription(self) -> None:
        """Update the IR receiver subscription when availability changes."""
        ir_state = self.hass.states.get(self._infrared_entity_id)
        self._attr_available = (
            ir_state is not None and ir_state.state != STATE_UNAVAILABLE
        )

        if not self._attr_available:
            self._async_unsubscribe_receiver()
        elif self._remove_signal_subscription is None:
            _LOGGER.debug(
                "Subscribing to infrared receiver entity %s for %s",
                self._infrared_entity_id,
                self.entity_id,
            )
            self._remove_signal_subscription = async_subscribe_receiver(
                self.hass, self._infrared_entity_id, self._handle_signal
            )

    @callback
    def _async_ir_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle infrared entity state changes."""
        self._async_update_receiver_subscription()
        self.async_write_ha_state()
