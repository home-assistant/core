"""Platform for binary_sensor."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import COORDINATOR_ADVANCED, COORDINATOR_CHARGESESSIONS
from .entity import OhmeEntity
from .utils import in_slot

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors and configure coordinator."""
    client = config_entry.runtime_data.client

    coordinator = config_entry.runtime_data.coordinators[COORDINATOR_CHARGESESSIONS]
    coordinator_advanced = config_entry.runtime_data.coordinators[COORDINATOR_ADVANCED]

    sensors = [
        ConnectedBinarySensor(coordinator, hass, client),
        ChargingBinarySensor(coordinator, hass, client),
        PendingApprovalBinarySensor(coordinator, hass, client),
        CurrentSlotBinarySensor(coordinator, hass, client),
        ChargerOnlineBinarySensor(coordinator_advanced, hass, client),
    ]

    async_add_entities(sensors, update_before_add=True)


class ConnectedBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if car is plugged in."""

    _attr_translation_key = "car_connected"
    _attr_icon = "mdi:ev-plug-type2"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    @property
    def is_on(self) -> bool:
        """Calculate state."""

        return bool(
            self.coordinator.data and self.coordinator.data["mode"] != "DISCONNECTED"
        )


class ChargingBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if car is charging."""

    _attr_translation_key = "car_charging"
    _attr_icon = "mdi:battery-charging-100"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def is_on(self) -> bool:
        """Return state."""

        return bool(
            self.coordinator.data and self.coordinator.data["power"]["watt"] > 0
        )


class PendingApprovalBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if a charge is pending approval."""

    _attr_translation_key = "pending_approval"
    _attr_icon = "mdi:alert-decagram"

    @property
    def is_on(self) -> bool:
        """Calculate state."""

        return bool(
            self.coordinator.data
            and self.coordinator.data["mode"] == "PENDING_APPROVAL"
        )


class CurrentSlotBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if we are currently in a smart charge slot."""

    _attr_translation_key = "slot_active"
    _attr_icon = "mdi:calendar-check"

    @property
    def extra_state_attributes(self):
        """Attributes of the sensor."""
        now = utcnow()
        slots = self.platform.config_entry.runtime_data.slots

        return {
            "planned_dispatches": [x for x in slots if not x["end"] or x["end"] > now],
            "completed_dispatches": [x for x in slots if x["end"] < now],
        }

    @property
    def is_on(self) -> bool:
        """Return state."""

        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Are we in a charge slot? This is a bit slow so we only update on coordinator data update."""
        if self.coordinator.data is None:
            self._state = None
        elif self.coordinator.data["mode"] == "DISCONNECTED":
            self._state = False
        else:
            self._state = in_slot(self.coordinator.data)

        self._last_updated = utcnow()

        self.async_write_ha_state()


class ChargerOnlineBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if charger is online."""

    _attr_translation_key = "charger_online"
    _attr_icon = "mdi:web"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self):
        """Calculate state."""

        if self.coordinator.data:
            return self.coordinator.data.get("online", False)
        return None
