"""
Support for Wink sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.wink/
"""
import logging

from homeassistant.const import (CONF_ACCESS_TOKEN, STATE_CLOSED,
                                 STATE_OPEN, TEMP_CELSIUS,
                                 ATTR_BATTERY_LEVEL)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-wink==0.7.6']

SENSOR_TYPES = ['temperature', 'humidity']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    for sensor in pywink.get_sensors():
        if sensor.capability() in SENSOR_TYPES:
            add_devices([WinkSensorDevice(sensor)])

    add_devices(WinkEggMinder(eggtray) for eggtray in pywink.get_eggtrays())


class WinkSensorDevice(Entity):
    """Representation of a Wink sensor."""

    def __init__(self, wink):
        """Initialize the sensor."""
        self.wink = wink
        self.capability = self.wink.capability()
        self._battery = self.wink.battery_level
        if self.wink.UNIT == "°":
            self._unit_of_measurement = TEMP_CELSIUS
        else:
            self._unit_of_measurement = self.wink.UNIT

    @property
    def state(self):
        """Return the state."""
        if self.capability == "humidity":
            return self.wink.humidity_percentage()
        elif self.capability == "temperature":
            return self.wink.temperature_float()
        else:
            return STATE_OPEN if self.is_open else STATE_CLOSED

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unique_id(self):
        """Return the ID of this wink sensor."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the sensor if any."""
        return self.wink.name()

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    def update(self):
        """Update state of the sensor."""
        self.wink.update_state()

    @property
    def is_open(self):
        """Return true if door is open."""
        return self.wink.state()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery_level,
            }

    @property
    def _battery_level(self):
        """Return the battery level."""
        return self.wink.battery_level * 100


class WinkEggMinder(Entity):
    """Representation of a Wink Egg Minder."""

    def __init__(self, wink):
        """Initialize the sensor."""
        self.wink = wink
        self._battery = self.wink.battery_level

    @property
    def state(self):
        """Return the state."""
        return self.wink.state()

    @property
    def unique_id(self):
        """Return the id of this wink Egg Minder."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the Egg Minder if any."""
        return self.wink.name()

    def update(self):
        """Update state of the Egg Minder."""
        self.wink.update_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery_level,
            }

    @property
    def _battery_level(self):
        """Return the battery level."""
        return self.wink.battery_level * 100
