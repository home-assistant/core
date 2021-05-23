"""Platform for binary sensor integration."""
import logging

from smarttub import SpaReminder
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.helpers import entity_platform

from .const import ATTR_REMINDERS, DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity, SmartTubSensorBase

_LOGGER = logging.getLogger(__name__)

# whether the reminder has been snoozed (bool)
ATTR_REMINDER_SNOOZED = "snoozed"

# how many days to snooze the reminder for
ATTR_SNOOZE_DAYS = "days"
SNOOZE_REMINDER_SCHEMA = {
    vol.Required(ATTR_SNOOZE_DAYS): vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
}


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

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        "snooze_reminder",
        SNOOZE_REMINDER_SCHEMA,
        "async_snooze",
    )


class SmartTubOnline(SmartTubSensorBase, BinarySensorEntity):
    """A binary sensor indicating whether the spa is currently online (connected to the cloud)."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Online", "online")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry.

        This seems to be very noisy and not generally useful, so disable by default.
        """
        return False

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
        return self.coordinator.data[self.spa.id][ATTR_REMINDERS][self.reminder_id]

    @property
    def is_on(self) -> bool:
        """Return whether the specified maintenance action needs to be taken."""
        return self.reminder.remaining_days == 0

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_REMINDER_SNOOZED: self.reminder.snoozed,
        }

    @property
    def device_class(self) -> str:
        """Return the device class for this entity."""
        return DEVICE_CLASS_PROBLEM

    async def async_snooze(self, **kwargs):
        """Snooze this reminder for the specified number of days."""
        days = kwargs[ATTR_SNOOZE_DAYS]
        await self.reminder.snooze(days)
        await self.coordinator.async_request_refresh()
