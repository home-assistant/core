"""
Support for Wink sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.wink/
"""
import logging

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.components.wink import WinkDevice
from homeassistant.loader import get_component

DEPENDENCIES = ['wink']

SENSOR_TYPES = ['temperature', 'humidity', 'balance', 'proximity']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink platform."""
    import pywink

    for sensor in pywink.get_sensors():
        if sensor.capability() in SENSOR_TYPES:
            add_devices([WinkSensorDevice(sensor, hass)])

    for eggtray in pywink.get_eggtrays():
        add_devices([WinkEggMinder(eggtray, hass)])

    for piggy_bank in pywink.get_piggy_banks():
        try:
            if piggy_bank.capability() in SENSOR_TYPES:
                add_devices([WinkSensorDevice(piggy_bank, hass)])
        except AttributeError:
            logging.getLogger(__name__).info("Device is not a sensor")


class WinkSensorDevice(WinkDevice, Entity):
    """Representation of a Wink sensor."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        super().__init__(wink, hass)
        wink = get_component('wink')
        self.capability = self.wink.capability()
        if self.wink.UNIT == '°':
            self._unit_of_measurement = TEMP_CELSIUS
        else:
            self._unit_of_measurement = self.wink.UNIT

    @property
    def state(self):
        """Return the state."""
        state = None
        if self.capability == 'humidity':
            if self.wink.humidity_percentage() is not None:
                state = round(self.wink.humidity_percentage())
        elif self.capability == 'temperature':
            if self.wink.temperature_float() is not None:
                state = round(self.wink.temperature_float(), 1)
        elif self.capability == 'balance':
            if self.wink.balance() is not None:
                state = round(self.wink.balance() / 100, 2)
        elif self.capability == 'proximity':
            if self.wink.proximity_float() is not None:
                state = self.wink.proximity_float()
        else:
            # A sensor should never get here, anything that does
            # will require an update to python-wink
            logging.getLogger(__name__).error("Please report this as an issue")
            state = None
        return state

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement


class WinkEggMinder(WinkDevice, Entity):
    """Representation of a Wink Egg Minder."""

    def __init__(self, wink, hass):
        """Initialize the sensor."""
        WinkDevice.__init__(self, wink, hass)

    @property
    def state(self):
        """Return the state."""
        return self.wink.state()
