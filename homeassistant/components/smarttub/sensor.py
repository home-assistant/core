"""Platform for sensor integration."""
from datetime import datetime, timedelta
from enum import Enum
import logging

from smarttub import SpaReminder

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubSensorBase

_LOGGER = logging.getLogger(__name__)

# the desired duration, in hours, of the cycle
ATTR_DURATION = "duration"
ATTR_CYCLE_LAST_UPDATED = "cycle_last_updated"
ATTR_MODE = "mode"
# the hour of the day at which to start the cycle (0-23)
ATTR_START_HOUR = "start_hour"
# whether the reminder has been snoozed (bool)
ATTR_REMINDER_SNOOZED = "snoozed"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor entities for the sensors in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = []
    for spa in controller.spas:
        entities.extend(
            [
                SmartTubSensor(controller.coordinator, spa, "State", "state"),
                SmartTubSensor(
                    controller.coordinator, spa, "Flow Switch", "flow_switch"
                ),
                SmartTubSensor(controller.coordinator, spa, "Ozone", "ozone"),
                SmartTubSensor(controller.coordinator, spa, "UV", "uv"),
                SmartTubSensor(
                    controller.coordinator, spa, "Blowout Cycle", "blowout_cycle"
                ),
                SmartTubSensor(
                    controller.coordinator, spa, "Cleanup Cycle", "cleanup_cycle"
                ),
                SmartTubPrimaryFiltrationCycle(controller.coordinator, spa),
                SmartTubSecondaryFiltrationCycle(controller.coordinator, spa),
            ]
        )
        entities.extend(
            SmartTubReminder(controller.coordinator, spa, reminder)
            for reminder in await spa.get_reminders()
        )

    async_add_entities(entities)


class SmartTubSensor(SmartTubSensorBase):
    """Generic class for SmartTub status sensors."""

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        if isinstance(self._state, Enum):
            return self._state.name.lower()
        return self._state.lower()


class SmartTubPrimaryFiltrationCycle(SmartTubSensorBase):
    """The primary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Primary Filtration Cycle", "primary_filtration"
        )

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.status.name.lower()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = self._state
        return {
            ATTR_DURATION: state.duration,
            ATTR_CYCLE_LAST_UPDATED: state.last_updated.isoformat(),
            ATTR_MODE: state.mode.name.lower(),
            ATTR_START_HOUR: state.start_hour,
        }


class SmartTubSecondaryFiltrationCycle(SmartTubSensorBase):
    """The secondary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Secondary Filtration Cycle", "secondary_filtration"
        )

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.status.name.lower()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = self._state
        return {
            ATTR_CYCLE_LAST_UPDATED: state.last_updated.isoformat(),
            ATTR_MODE: state.mode.name.lower(),
        }


class SmartTubReminder(SmartTubSensorBase):
    """Reminders for maintenance actions."""

    def __init__(self, coordinator, spa, reminder):
        """Initialize the entity."""
        super().__init__(
            coordinator,
            spa,
            f"{reminder.name.capitalize()} Reminder",
            "reminder_{reminder.id.lower()}",
        )
        self.reminder_id = reminder.id

    @property
    def unique_id(self):
        """Return a unique id for this sensor."""
        return f"{self.spa.id}-reminder-{self.reminder_id}"

    @property
    def reminder(self) -> SpaReminder:
        """Return the underlying SpaPump object for this entity."""
        return self.coordinator.data[self.spa.id]["reminders"][self.reminder_id]

    @property
    def state(self) -> str:
        """Return the datetime at which the reminder will activate."""
        when = datetime.now() + timedelta(days=self.reminder.remaining_days)
        return when.isoformat()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_REMINDER_SNOOZED: self.reminder.snoozed,
        }
