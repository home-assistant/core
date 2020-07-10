"""Platform for binary sensor integration."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_BATTERY_CHARGING, ATTR_BATTERY_LEVEL

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS = [
    ("Charging", "battery_charging", "mdi:ev-station"),
    ("Connected", "connectivity", "mdi:car-connected"),
    ("Power", "power", "mdi:power"),
    ("Lock", "lock", "mdi:lock"),
]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    entities = []
    for vehicle in hass.data[DOMAIN].account.get_vehicles():
        for sensor in SENSORS:
            device = NiuBinarySensor(
                hass.data[DOMAIN], vehicle, sensor[0], sensor[1], sensor[2]
            )
            entities.append(device)

    add_entities(entities, True)


class NiuBinarySensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, account, vehicle, attribute, device_class, icon):
        """Initialize the sensor."""
        self._account = account
        self._serial = vehicle.get_serial()
        self._vehicle = vehicle

        self._attribute = attribute
        self._device_class = device_class
        self._icon = icon

        self._state = None

    @property
    def unique_id(self) -> str:
        """Return the unique id for the sensor."""
        return f"{self._serial}_{self._attribute}"

    @property
    def should_poll(self) -> bool:
        """Return false since data update is centralized in NiuAccount."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._vehicle.get_name()} {self._attribute}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_BATTERY_LEVEL: self._vehicle.get_soc(),
            ATTR_BATTERY_CHARGING: self._vehicle.is_charging(),
        }

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": (DOMAIN, self._serial),
            "name": self._vehicle.get_name(),
            "manufacturer": "NIU",
            "model": self._vehicle.get_model(),
        }

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register state update callback."""

        self._account.add_update_listener(self.update_callback)

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        # Update local vehicle reference
        self._vehicle = next(
            (
                veh
                for veh in self._account.account.get_vehicles()
                if veh.get_serial() == self._serial
            ),
            None,
        )

        if self._vehicle is None:
            _LOGGER.error("Scooter %s has been removed from the cloud", self._serial)

        _LOGGER.debug("Updating %s", self.name)

        if self._attribute == "Charging":
            self._state = self._vehicle.is_charging()

        if self._attribute == "Connected":
            self._state = self._vehicle.is_connected()

        if self._attribute == "Power":
            self._state = self._vehicle.is_on()

        if self._attribute == "Lock":
            self._state = not self._vehicle.is_locked()
