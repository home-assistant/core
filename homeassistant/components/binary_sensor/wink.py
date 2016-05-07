"""
Support for Wink sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.wink/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_ACCESS_TOKEN, ATTR_BATTERY_LEVEL
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-wink==0.7.6']

# These are the available sensors mapped to binary_sensor class
SENSOR_TYPES = {
    "opened": "opening",
    "brightness": "light",
    "vibration": "vibration",
    "loudness": "sound"
}


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
            add_devices([WinkBinarySensorDevice(sensor)])


class WinkBinarySensorDevice(BinarySensorDevice, Entity):
    """Representation of a Wink sensor."""

    def __init__(self, wink):
        """Initialize the Wink binary sensor."""
        self.wink = wink
        self._unit_of_measurement = self.wink.UNIT
        self._battery = self.wink.battery_level
        self.capability = self.wink.capability()

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.capability == "loudness":
            return self.wink.loudness_boolean()
        elif self.capability == "vibration":
            return self.wink.vibration_boolean()
        elif self.capability == "brightness":
            return self.wink.brightness_boolean()
        else:
            return self.wink.state()

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return SENSOR_TYPES.get(self.capability)

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
