"""Demo platform that offers a fake infrared receiver event entity."""

from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    INFRARED_CMD_POWER_OFF,
    INFRARED_CMD_POWER_ON,
    INFRARED_CMD_SPEED_HIGH,
    INFRARED_CMD_SPEED_LOW,
    INFRARED_CMD_SPEED_MEDIUM,
    INFRARED_FAN_ADDRESS,
)

PARALLEL_UPDATES = 0

COMMAND_EVENTS = {
    INFRARED_CMD_POWER_ON: "power_on",
    INFRARED_CMD_POWER_OFF: "power_off",
    INFRARED_CMD_SPEED_LOW: "speed_low",
    INFRARED_CMD_SPEED_MEDIUM: "speed_medium",
    INFRARED_CMD_SPEED_HIGH: "speed_high",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo infrared event platform."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "infrared_fan":
            continue
        if subentry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID) is None:
            continue
        async_add_entities(
            [
                DemoInfraredEvent(
                    subentry_id=subentry_id,
                    device_name=subentry.title,
                    infrared_receiver_entity_id=subentry.data[
                        CONF_INFRARED_RECEIVER_ENTITY_ID
                    ],
                )
            ],
            config_subentry_id=subentry_id,
        )


class DemoInfraredEvent(InfraredReceiverConsumerEntity, EventEntity):
    """Representation of a demo infrared event entity."""

    _attr_has_entity_name = True
    _attr_name = "Received IR Event"
    _attr_event_types = list(COMMAND_EVENTS.values())

    def __init__(
        self, subentry_id: str, device_name: str, infrared_receiver_entity_id: str
    ) -> None:
        """Initialize the demo infrared event entity."""
        self._infrared_receiver_entity_id = infrared_receiver_entity_id
        self._attr_unique_id = subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)}, name=device_name
        )

    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""
        command = NECCommand.from_raw_timings(signal.timings)
        if command is None or command.address != INFRARED_FAN_ADDRESS:
            return
        event_type = COMMAND_EVENTS.get(command.command)
        if event_type is None:
            return
        self._trigger_event(event_type, {"raw_code": signal.timings})
        self.async_write_ha_state()
