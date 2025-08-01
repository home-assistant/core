"""Platform for binary sensor integration."""

from __future__ import annotations

import logging
from typing import Any

from smarttub import Spa, SpaError, SpaReminder
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ATTR_ERRORS, ATTR_REMINDERS, ATTR_SENSORS
from .controller import SmartTubConfigEntry
from .entity import (
    SmartTubEntity,
    SmartTubExternalSensorBase,
    SmartTubOnboardSensorBase,
)

# whether the reminder has been snoozed (bool)
ATTR_REMINDER_SNOOZED = "snoozed"

ATTR_ERROR_CODE = "error_code"
ATTR_ERROR_TITLE = "error_title"
ATTR_ERROR_DESCRIPTION = "error_description"
ATTR_ERROR_TYPE = "error_type"
ATTR_CREATED_AT = "created_at"
ATTR_UPDATED_AT = "updated_at"

# how many days to snooze the reminder for
ATTR_REMINDER_DAYS = "days"
RESET_REMINDER_SCHEMA: VolDictType = {
    vol.Required(ATTR_REMINDER_DAYS): vol.All(
        vol.Coerce(int), vol.Range(min=30, max=365)
    )
}
SNOOZE_REMINDER_SCHEMA: VolDictType = {
    vol.Required(ATTR_REMINDER_DAYS): vol.All(
        vol.Coerce(int), vol.Range(min=10, max=120)
    )
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartTubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities for the binary sensors in the tub."""

    controller = entry.runtime_data

    entities: list[BinarySensorEntity] = []
    for spa in controller.spas:
        entities.append(SmartTubOnline(controller.coordinator, spa))
        entities.append(SmartTubError(controller.coordinator, spa))
        entities.extend(
            SmartTubReminder(controller.coordinator, spa, reminder)
            for reminder in controller.coordinator.data[spa.id][ATTR_REMINDERS].values()
        )
        for sensor in controller.coordinator.data[spa.id][ATTR_SENSORS].values():
            name = sensor.name.strip("{}")
            if name.startswith("cover-"):
                entities.append(
                    SmartTubCoverSensor(controller.coordinator, spa, sensor)
                )

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "snooze_reminder",
        SNOOZE_REMINDER_SCHEMA,
        "async_snooze",
    )
    platform.async_register_entity_service(
        "reset_reminder",
        RESET_REMINDER_SCHEMA,
        "async_reset",
    )


class SmartTubOnline(SmartTubOnboardSensorBase, BinarySensorEntity):
    """A binary sensor indicating whether the spa is currently online (connected to the cloud)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    # This seems to be very noisy and not generally useful, so disable by default.
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: DataUpdateCoordinator[dict[str, Any]], spa: Spa
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Online", "online")

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state is True


class SmartTubReminder(SmartTubEntity, BinarySensorEntity):
    """Reminders for maintenance actions."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        spa: Spa,
        reminder: SpaReminder,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            spa,
            f"{reminder.name.title()} Reminder",
        )
        self.reminder_id = reminder.id
        self._attr_unique_id = f"{spa.id}-reminder-{reminder.id}"

    @property
    def reminder(self) -> SpaReminder:
        """Return the underlying SpaReminder object for this entity."""
        return self.coordinator.data[self.spa.id][ATTR_REMINDERS][self.reminder_id]

    @property
    def is_on(self) -> bool:
        """Return whether the specified maintenance action needs to be taken."""
        return self.reminder.remaining_days == 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_REMINDER_SNOOZED: self.reminder.snoozed,
            ATTR_REMINDER_DAYS: self.reminder.remaining_days,
        }

    async def async_snooze(self, days):
        """Snooze this reminder for the specified number of days."""
        await self.reminder.snooze(days)
        await self.coordinator.async_request_refresh()

    async def async_reset(self, days):
        """Dismiss this reminder, and reset it to the specified number of days."""
        await self.reminder.reset(days)
        await self.coordinator.async_request_refresh()


class SmartTubError(SmartTubEntity, BinarySensorEntity):
    """Indicates whether an error code is present.

    There may be 0 or more errors. If there are >0, we show the first one.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: DataUpdateCoordinator[dict[str, Any]], spa: Spa
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            spa,
            "Error",
        )

    @property
    def error(self) -> SpaError | None:
        """Return the underlying SpaError object for this entity."""
        errors = self.coordinator.data[self.spa.id][ATTR_ERRORS]
        if len(errors) == 0:
            return None
        return errors[0]

    @property
    def is_on(self) -> bool:
        """Return true if an error is signaled."""
        return self.error is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if (error := self.error) is None:
            return {}

        return {
            ATTR_ERROR_CODE: error.code,
            ATTR_ERROR_TITLE: error.title,
            ATTR_ERROR_DESCRIPTION: error.description,
            ATTR_ERROR_TYPE: error.error_type,
            ATTR_CREATED_AT: error.created_at.isoformat(),
            ATTR_UPDATED_AT: error.updated_at.isoformat(),
        }


class SmartTubCoverSensor(SmartTubExternalSensorBase, BinarySensorEntity):
    """Wireless magnetic cover sensor."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    @property
    def is_on(self) -> bool:
        """Return False if the cover is closed, True if open."""
        # magnet is True when the cover is closed, False when open
        # device class OPENING wants True to mean open, False to mean closed
        return not self.sensor.magnet
