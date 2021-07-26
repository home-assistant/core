"""Support for Flipr binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from . import FliprEntity
from .const import CONF_FLIPR_ID, DOMAIN

BINARY_SENSORS = {
    "ph_status": {
        "unit": None,
        "icon": None,
        "name": "PH Status",
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    "chlorine_status": {
        "unit": None,
        "icon": None,
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
            FliprBinarySensor(
                coordinator, config_entry.data[CONF_FLIPR_ID], binary_sensor
            )
        )

    async_add_entities(binary_sensors_list, True)


class FliprBinarySensor(FliprEntity, BinarySensorEntity):
    """Representation of Flipr binary sensors."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on in case of a Problem is detected."""
        return (
            self.coordinator.data[self.info_type] == "TooLow"
            or self.coordinator.data[self.info_type] == "TooHigh"
        )

    @property
    def icon(self):
        """Return the icon."""
        return BINARY_SENSORS[self.info_type]["icon"]

    @property
    def device_class(self):
        """Return the class of this device."""
        return BINARY_SENSORS[self.info_type]["device_class"]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"Flipr {self.flipr_id} {BINARY_SENSORS[self.info_type]['name']}"
