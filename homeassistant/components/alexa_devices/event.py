"""Support for events."""

from typing import Final

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

EVENTS: Final = {
    EventEntityDescription(
        key="voice_event",
        translation_key="voice_event",
    ),
}

EVENT_TYPE = "triggered"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices events based on a config entry."""
    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AlexaVoiceEvent(coordinator, serial_num, event_desc)
                for event_desc in EVENTS
                for serial_num in new_devices
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AlexaVoiceEvent(AmazonEntity, EventEntity):
    """Representation of an Alexa voice event."""

    _attr_event_types = [EVENT_TYPE]
    coordinator: AmazonDevicesCoordinator
    _last_seen_timestamp: int = 0  #  January 1, 1970 at 12:00:00 AM

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if not (
            vocal_record := self.coordinator.vocal_records.get(
                self.device.serial_number
            )
        ):
            _LOGGER.debug(
                "No vocal record found for device %s [%s]",
                self.device.account_name,
                self.device.serial_number,
            )
            return

        if vocal_record.timestamp <= self._last_seen_timestamp:
            # Discard old events that have already been processed
            return

        self._last_seen_timestamp = vocal_record.timestamp
        self._trigger_event(
            EVENT_TYPE,
            {
                "intent": vocal_record.intent,
                "voice_command": vocal_record.title,
                "voice_reply": vocal_record.sub_title,
            },
        )
        self.async_write_ha_state()
