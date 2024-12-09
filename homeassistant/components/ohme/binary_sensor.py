"""Platform for binary_sensor."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR_ADVANCED, COORDINATOR_CHARGESESSIONS
from .entity import OhmeEntity

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
            self.coordinator.data
            and self.coordinator.data["power"]
            and self.coordinator.data["power"]["watt"] > 0
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
