"""Platform for binary sensor integration."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
)

from . import DOMAIN, NiuVehicle

_LOGGER = logging.getLogger(__name__)


SENSORS = {
    "charging": ("Charging Status", DEVICE_CLASS_BATTERY_CHARGING, "mdi:ev-station"),
    "connection": ("Connection Status", DEVICE_CLASS_CONNECTIVITY, "mdi:car-connected"),
    "power": ("Power Status", DEVICE_CLASS_POWER, "mdi:power"),
    "lock": ("Lock Status", DEVICE_CLASS_LOCK, "mdi:lock"),
}


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""

    entities = []

    for serial in hass.data[DOMAIN][config.entry_id]["account"].get_vehicles():
        for key, value in SENSORS.items():
            entities.append(
                NiuBinarySensor(
                    serial,
                    hass.data[DOMAIN][config.entry_id]["coordinator"],
                    key,
                    value[0],
                    value[1],
                    value[2],
                )
            )

    async_add_entities(entities, True)


class NiuBinarySensor(NiuVehicle, BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, vehicle_id, coordinator, attribute, name, device_class, icon):
        """Initialize the sensor."""
        super().__init__(vehicle_id, coordinator)

        self._attribute = attribute
        self._name = name
        self._device_class = device_class
        self._icon = icon

    @property
    def unique_id(self) -> str:
        """Return the unique id for the sensor."""
        return f"{self._vehicle.serial_number}_{self._attribute}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._vehicle.name} {self._name}"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the sensor."""
        if self._attribute == "charging":
            return self._vehicle.is_charging

        if self._attribute == "connection":
            return self._vehicle.is_connected

        if self._attribute == "power":
            return self._vehicle.is_on

        if self._attribute == "lock":
            return not self._vehicle.is_locked

        return None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon
