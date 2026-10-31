"""Support for Flo Water Monitor alert events."""

from typing import override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FloConfigEntry, FloDeviceDataUpdateCoordinator
from .entity import FloEntity

EVENT_TYPES = ["info", "warning", "critical"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flo alert events from config entry."""
    async_add_entities(
        FloAlertEvent(device)
        for device in config_entry.runtime_data.devices
        if device.device_type != "puck_oem"
    )


class FloAlertEvent(FloEntity, EventEntity):
    """Event entity that fires when Flo raises a new alert.

    The pending alerts binary sensor stays on while any alert is undismissed,
    so it cannot signal alerts raised after the first one.
    """

    _attr_event_types = EVENT_TYPES
    _attr_translation_key = "alert"

    def __init__(self, device: FloDeviceDataUpdateCoordinator) -> None:
        """Initialize the alert event."""
        super().__init__("alert", device)
        # Alerts already pending at startup are not new and must not fire.
        self._seen_counts = {
            alarm_id: count for alarm_id, (_, count) in device.pending_alarms.items()
        }

    @property
    @override
    def available(self) -> bool:
        """Return True if Flo's cloud is reachable.

        Alerts come from the cloud and can concern a device that is offline.
        """
        return self._device.last_update_success

    @override
    async def async_added_to_hass(self) -> None:
        """Register the coordinator listener."""
        await super().async_added_to_hass()
        self.async_on_remove(self._device.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Fire an event for each alert that is new or has occurred again."""
        alarms = self._device.pending_alarms
        for alarm_id, (severity, count) in alarms.items():
            if count <= self._seen_counts.get(alarm_id, 0):
                continue
            self._trigger_event(
                severity if severity in EVENT_TYPES else "info",
                {"alarm_id": alarm_id, "count": count},
            )
            # An event entity only keeps its latest event, so write each one.
            self.async_write_ha_state()
        self._seen_counts = {alarm_id: count for alarm_id, (_, count) in alarms.items()}
