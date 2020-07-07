"""Support for PoolSense binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from . import PoolSenseEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS = {
    "pH Status": {
        "unit": None,
        "icon": "mdi:pool",
        "name": "pH Status",
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    "Chlorine Status": {
        "unit": "",
        "icon": "mdi:pool",
        "name": "Chlorine Status",
        "device_class": DEVICE_CLASS_PROBLEM,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    binary_sensors_list = []
    for binary_sensor in BINARY_SENSORS:
        binary_sensors_list.append(
            PoolSenseBinarySensor(
                coordinator,
                config_entry.data[CONF_EMAIL],
                config_entry.data[CONF_PASSWORD],
                binary_sensor,
            )
        )

    async_add_entities(binary_sensors_list, False)


class PoolSenseBinarySensor(PoolSenseEntity, BinarySensorEntity):
    """Representation of PoolSense binary sensors."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.coordinator.data[self.info_type] == "green"

    @property
    def icon(self):
        """Return the icon."""
        if self.info_type == "pH Status":
            if self.coordinator.data[self.info_type] == "red":
                return "mdi:thumb-down"
            return "mdi:thumb-up"
        if self.info_type == "Chlorine Status":
            if self.coordinator.data[self.info_type] == "red":
                return "mdi:thumb-down"
            return "mdi:thumb-up"
        return BINARY_SENSORS[self.info_type]["icon"]

    @property
    def device_class(self):
        """Return the class of this device."""
        return BINARY_SENSORS[self.info_type]["device_class"]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"PoolSense {BINARY_SENSORS[self.info_type]['name']}"
