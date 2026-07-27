"""Event platform for LED Infrared integration."""

import logging
from typing import cast, override

from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_RECEIVER_ENTITY_ID, LEDIrDeviceType
from .entity import LEDIrBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LED IR event entity from config entry."""
    if not (receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID)):
        return
    async_add_entities(
        [LEDIrEventEntity(entry, entry.data[CONF_DEVICE_TYPE], receiver_entity_id)]
    )


class LEDIrEventEntity(LEDIrBaseEntity, InfraredReceiverConsumerEntity, EventEntity):
    """Event entity that fires when an LED IR command is received."""

    _attr_translation_key = "received_command"

    def __init__(
        self, entry: ConfigEntry, device_type: LEDIrDeviceType, receiver_entity_id: str
    ) -> None:
        """Initialize the event entity."""
        super().__init__(entry, device_type)
        self._attr_unique_id = entry.entry_id
        self._infrared_receiver_entity_id = receiver_entity_id

        self._attr_event_types = [command.name.lower() for command in self._codes]

    @callback
    @override
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""
        command_received = NECCommand.from_raw_timings(signal.timings)
        if command_received is None:
            return

        try:
            command_code = self._codes(command_received.command)
        except ValueError:
            return

        expected_command = cast(NECCommand, command_code.to_command())
        if command_received.address != expected_command.address:
            return

        event_type = command_code.name.lower()

        _LOGGER.debug(
            "Received IR command: %s (0x%02X)", event_type, command_received.command
        )

        self._trigger_event(event_type)
        async_dispatcher_send(self.hass, self._entry.entry_id, event_type)
        self.async_write_ha_state()
