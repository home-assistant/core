"""Platform for binary sensor integration."""
import logging

from niu import NiuCloud

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
    print("Setting up binary sensor")

    entities = []

    for vehicle in hass.data[DOMAIN][config.entry_id]["account"].get_vehicles():
        for key, value in SENSORS.items():
            entities.append(
                NiuBinarySensor(
                    hass.data[DOMAIN][config.entry_id]["account"],
                    vehicle,
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

    def __init__(self, niu, vehicle, coordinator, attribute, name, device_class, icon):
        """Initialize the sensor."""
        super().__init__(niu, vehicle, coordinator)

        self._attribute = attribute
        self._name = name
        self._device_class = device_class
        self._icon = icon

        self._state = None

    @property
    def unique_id(self) -> str:
        """Return the unique id for the sensor."""
        return f"{self.vehicle.serial_number}_{self._attribute}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.vehicle.name} {self._name}"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    # async def async_update(self) -> None:
    #    """Fetch new state data for the sensor.

    #    This is the only method that should fetch new data for Home Assistant.
    #    """
    #    await super().async_update()
    #    print("UPDATE ENTITY DATA")
    #    # Update local vehicle reference
    #    self.vehicle = next(
    #        (
    #            veh
    #            for veh in self.niu.get_vehicles()
    #            if veh.serial_number == self.vehicle.serial_number
    #        ),
    #        None,
    #    )

    #    if self.vehicle is None:
    #        _LOGGER.error(
    #            "Scooter %s has been removed from the cloud", self.vehicle.serial_number
    #        )

    #    _LOGGER.debug("Updating %s", self.name)

    #    if self._attribute == "charging":
    #        self._state = self.vehicle.is_charging

    #    if self._attribute == "connection":
    #        self._state = self.vehicle.is_connected

    #    if self._attribute == "power":
    #        self._state = self.vehicle.is_on

    #    if self._attribute == "lock":
    #        self._state = not self.vehicle.is_locked
    #        if self._state:
    #            self._icon = "mdi:lock-open"
    #        else:
    #            self._icon = "mdi:lock"
