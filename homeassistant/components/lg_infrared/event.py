"""Event platform for LG IR integration."""

import logging
from typing import override

from infrared_protocols.codes.lg.tv import LG_ADDRESS, LGTVCode
from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_RECEIVER_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_COMMAND_CODE_TO_EVENT_TYPE: dict[LGTVCode, str] = {
    LGTVCode.ASPECT: "aspect",
    LGTVCode.BACK: "back",
    LGTVCode.BLUE: "blue",
    LGTVCode.CHANNEL_DOWN: "channel_down",
    LGTVCode.CHANNEL_UP: "channel_up",
    LGTVCode.EXIT: "exit",
    LGTVCode.EZ_ADJUST: "ez_adjust",
    LGTVCode.FAST_FORWARD: "fast_forward",
    LGTVCode.GREEN: "green",
    LGTVCode.GUIDE: "guide",
    LGTVCode.HDMI_1: "hdmi_1",
    LGTVCode.HDMI_2: "hdmi_2",
    LGTVCode.HDMI_3: "hdmi_3",
    LGTVCode.HDMI_4: "hdmi_4",
    LGTVCode.HOME: "home",
    LGTVCode.INFO: "info",
    LGTVCode.INPUT: "input",
    LGTVCode.IN_START: "in_start",
    LGTVCode.LIST: "list",
    LGTVCode.MENU: "menu",
    LGTVCode.MUTE: "mute",
    LGTVCode.NAV_DOWN: "nav_down",
    LGTVCode.NAV_LEFT: "nav_left",
    LGTVCode.NAV_RIGHT: "nav_right",
    LGTVCode.NAV_UP: "nav_up",
    LGTVCode.NUM_0: "num_0",
    LGTVCode.NUM_1: "num_1",
    LGTVCode.NUM_2: "num_2",
    LGTVCode.NUM_3: "num_3",
    LGTVCode.NUM_4: "num_4",
    LGTVCode.NUM_5: "num_5",
    LGTVCode.NUM_6: "num_6",
    LGTVCode.NUM_7: "num_7",
    LGTVCode.NUM_8: "num_8",
    LGTVCode.NUM_9: "num_9",
    LGTVCode.OK: "ok",
    LGTVCode.PAUSE: "pause",
    LGTVCode.PLAY: "play",
    LGTVCode.POWER: "power",
    LGTVCode.POWER_OFF: "power_off",
    LGTVCode.POWER_ON: "power_on",
    LGTVCode.RED: "red",
    LGTVCode.REWIND: "rewind",
    LGTVCode.SAP: "sap",
    LGTVCode.SETTINGS: "settings",
    LGTVCode.STOP: "stop",
    LGTVCode.SUBTITLE: "subtitle",
    LGTVCode.TEXT: "text",
    LGTVCode.VOLUME_DOWN: "volume_down",
    LGTVCode.VOLUME_UP: "volume_up",
    LGTVCode.YELLOW: "yellow",
}
_EVENT_TYPE_UNKNOWN = "unknown"
_EVENT_TYPES: list[str] = [*_COMMAND_CODE_TO_EVENT_TYPE.values(), _EVENT_TYPE_UNKNOWN]


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

    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""
        nec_command = NECCommand.from_raw_timings(signal.timings)
        if nec_command is None:
            return

        if nec_command.address != LG_ADDRESS:
            return

        try:
            command_code = LGTVCode(nec_command.command)
        except ValueError:
            # Ensure that a future change to the LGTVCode enum doesn't break this and
            # shows as unknown
            event_type = _EVENT_TYPE_UNKNOWN
        else:
            event_type = _COMMAND_CODE_TO_EVENT_TYPE.get(
                command_code, _EVENT_TYPE_UNKNOWN
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
        if not self.available:
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

    @override
    @callback
    def _async_ir_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle infrared entity state changes."""
        super()._async_ir_state_changed(event)
        self._async_update_receiver_subscription()
