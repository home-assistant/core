"""Platform for binary sensor integration."""
from datetime import datetime, timedelta
import logging

from smarttub import SpaReminder

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from .const import ATTR_REMINDERS, DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity, SmartTubSensorBase

_LOGGER = logging.getLogger(__name__)

# whether the reminder has been snoozed (bool)
ATTR_REMINDER_SNOOZED = "snoozed"
# the date at which the reminder will be activated
ATTR_REMINDER_DATE = "date"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up binary sensor entities for the binary sensors in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = []
    for spa in controller.spas:
        entities.append(SmartTubOnline(controller.coordinator, spa))
        entities.extend(
            SmartTubReminder(controller.coordinator, spa, reminder)
            for reminder in controller.coordinator.data[spa.id][ATTR_REMINDERS].values()
        )

    async_add_entities(entities)


class SmartTubOnline(SmartTubSensorBase, BinarySensorEntity):
    """A binary sensor indicating whether the spa is currently online (connected to the cloud)."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Online", "online")

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state is True

    @property
    def device_class(self) -> str:
        """Return the device class for this entity."""
        return DEVICE_CLASS_CONNECTIVITY


class SmartTubReminder(SmartTubEntity, BinarySensorEntity):
    """Reminders for maintenance actions."""

    def __init__(self, coordinator, spa, reminder):
        """Initialize the entity."""
        super().__init__(
            coordinator,
            spa,
            f"{reminder.name.title()} Reminder",
        )
        self.reminder_id = reminder.id

    @property
    def unique_id(self):
        """Return a unique id for this sensor."""
        return f"{self.spa.id}-reminder-{self.reminder_id}"

    @property
    def reminder(self) -> SpaReminder:
        """Return the underlying SpaReminder object for this entity."""
        return self.coordinator.data[self.spa.id]["reminders"][self.reminder_id]

    @property
    def is_on(self) -> bool:
        """Return whether the specified maintenance action needs to be taken."""
        return self.reminder.remaining_days == 0

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        when = datetime.now() + timedelta(days=self.reminder.remaining_days)
        return {
            ATTR_REMINDER_SNOOZED: self.reminder.snoozed,
            ATTR_REMINDER_DATE: when.date().isoformat(),
        }

    @property
    def device_class(self) -> str:
        """Return the device class for this entity."""
        return DEVICE_CLASS_PROBLEM
