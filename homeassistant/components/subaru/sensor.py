"""Support for the Subaru sensors."""
import logging

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    TIME_MINUTES,
    UNIT_PERCENTAGE,
    VOLT,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util.distance import convert as dist_convert
from homeassistant.util.temperature import celsius_to_fahrenheit
from homeassistant.util.unit_system import IMPERIAL_SYSTEM
from homeassistant.util.volume import convert as vol_convert

from . import DOMAIN as SUBARU_DOMAIN, SubaruDevice

_LOGGER = logging.getLogger(__name__)
L_PER_GAL = vol_convert(1, VOLUME_GALLONS, VOLUME_LITERS)
KM_PER_MI = dist_convert(1, LENGTH_MILES, LENGTH_KILOMETERS)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Subaru sensors by config_entry."""
    controller = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["controller"]
    entities = []
    for device in hass.data[SUBARU_DOMAIN][config_entry.entry_id]["devices"]["sensor"]:
        entities.append(SubaruSensor(device, controller, config_entry, hass))
    async_add_entities(entities, True)


class SubaruSensor(SubaruDevice, Entity):
    """Representation of Subaru sensors."""

    def __init__(self, subaru_device, controller, config_entry, hass):
        """Initialize of the sensor."""
        self.current_value = None
        self.hass = hass
        self._unit_of_measurement = None
        super().__init__(subaru_device, controller, config_entry)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit_of_measurement

    async def async_update(self):
        """Update the state from the sensor."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        await super().async_update()
        self.units = self.hass.config.units
        self.current_value = self.subaru_device.get_value()

        if self.current_value is None:
            pass

        elif self.subaru_device.type == "External Temp":  # C
            if self.units == IMPERIAL_SYSTEM:
                self.current_value = round(
                    celsius_to_fahrenheit(float(self.current_value)), 1
                )
            self._unit_of_measurement = self.units.temperature_unit

        elif self.subaru_device.type == "Odometer":  # m
            if self.units == IMPERIAL_SYSTEM:
                self.current_value = round(
                    dist_convert(int(self.current_value), LENGTH_METERS, LENGTH_MILES),
                    1,
                )
            else:
                self.current_value = round(
                    dist_convert(
                        int(self.current_value), LENGTH_METERS, LENGTH_KILOMETERS
                    ),
                    1,
                )
            self._unit_of_measurement = self.units.length_unit

        elif self.subaru_device.type == "EV Range":  # mi
            if self.units == IMPERIAL_SYSTEM:
                pass
            else:
                self.current_value = round(
                    dist_convert(
                        int(self.current_value), LENGTH_MILES, LENGTH_KILOMETERS
                    ),
                    1,
                )
            self._unit_of_measurement = self.units.length_unit

        elif self.subaru_device.type == "Range":  # km
            if self.units == IMPERIAL_SYSTEM:
                self.current_value = round(
                    dist_convert(
                        int(self.current_value), LENGTH_KILOMETERS, LENGTH_MILES
                    ),
                    0,
                )
            self._unit_of_measurement = self.units.length_unit

        elif self.subaru_device.type == "EV Charge Rate":  # min
            self._unit_of_measurement = TIME_MINUTES

        elif self.subaru_device.type == "12V Battery Voltage":  # V
            self._unit_of_measurement = VOLT

        elif self.subaru_device.type == "Avg Fuel Consumption":  # L/10km
            if self.units == IMPERIAL_SYSTEM:
                self._unit_of_measurement = "mi/gal"
                self.current_value = (1000.0 * L_PER_GAL) / (
                    KM_PER_MI * float(self.current_value)
                )
                self.current_value = round(self.current_value, 1)
            else:
                self._unit_of_measurement = "L/100km"
                self.current_value = float(self.current_value) / 10.0

        elif self.subaru_device.type == "EV Battery Level":  # %
            self._unit_of_measurement = UNIT_PERCENTAGE

        else:
            _LOGGER.warning(
                "Unsupported Subaru Sensor Type %s" % self.subaru_device.type
            )
