"""Platform for binary_sensor."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import OhmeEntity

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="car_connected",
        name="Car Connected",
        icon="mdi:ev-plug-type2",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BinarySensorEntityDescription(
        key="car_charging",
        name="Car Charging",
        icon="mdi:battery-charging-100",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="pending_approval",
        name="Pending Approval",
        icon="mdi:alert-decagram",
    ),
    BinarySensorEntityDescription(
        key="charger_online",
        name="Charger Online",
        icon="mdi:web",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors and configure coordinator."""
    client = config_entry.runtime_data.client
    coordinator = config_entry.runtime_data.coordinator

    sensors = [
        OhmeBinarySensor(coordinator, hass, client, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(sensors, update_before_add=True)


class OhmeBinarySensor(OhmeEntity, BinarySensorEntity):
    """Generic binary sensor for Ohme."""

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        if not self.coordinator.data:
            return False

        handlers = {
            "car_connected": lambda: bool(
                self.coordinator.data.charge_sessions
                and self.coordinator.data.charge_sessions["mode"] != "DISCONNECTED"
            ),
            "car_charging": lambda: bool(
                self.coordinator.data.charge_sessions
                and self.coordinator.data.charge_sessions.get("power")
                and self.coordinator.data.charge_sessions["power"].get("watt", 0) > 0
            ),
            "pending_approval": lambda: bool(
                self.coordinator.data.charge_sessions
                and self.coordinator.data.charge_sessions["mode"] == "PENDING_APPROVAL"
            ),
            "charger_online": lambda: bool(
                self.coordinator.data.advanced_settings
                and self.coordinator.data.advanced_settings.get("online", False)
            ),
        }
        return handlers.get(self.entity_description.key, lambda: False)()
