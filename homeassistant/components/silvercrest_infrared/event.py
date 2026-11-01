"""Event platform for SilverCrest Infrared integration."""

import logging
from typing import cast, override

from infrared_protocols.codes.silvercrest.fan import SilverCrestFanCode
from infrared_protocols.commands.symphony import SymphonyCommand

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_RECEIVER_ENTITY_ID
from .entity import SilverCrestIrBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SilverCrest IR event entity from config entry."""
    if not entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        return
    async_add_entities([SilverCrestIrEventEntity(entry)])


class SilverCrestIrEventEntity(
    SilverCrestIrBaseEntity, InfraredReceiverConsumerEntity, EventEntity
):
    """Event entity that fires when a SilverCrest IR command is received."""

    _attr_translation_key = "received_command"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the event entity."""
        super().__init__(entry)
        self._attr_unique_id = entry.entry_id
        self._infrared_receiver_entity_id = entry.data[CONF_INFRARED_RECEIVER_ENTITY_ID]
        self._attr_event_types = [
            command.name.lower() for command in SilverCrestFanCode
        ]

    @callback
    @override
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""
        command_received = SymphonyCommand.from_raw_timings(signal.timings)
        if command_received is None:
            return

        try:
            command_code = SilverCrestFanCode(command_received.code)
        except ValueError:
            return

        expected_command = cast(SymphonyCommand, command_code.to_command())
        if command_received.code != expected_command.code:
            return

        event_type = command_code.name.lower()

        _LOGGER.debug(
            "Received IR command: %s (0x%02X)", event_type, command_received.code
        )

        self._trigger_event(event_type)
        async_dispatcher_send(self.hass, self._entry.entry_id, event_type)
        self.async_write_ha_state()
