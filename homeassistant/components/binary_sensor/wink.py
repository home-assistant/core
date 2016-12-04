"""
Support for Wink binary sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/binary_sensor.wink/
"""

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor.wink import WinkDevice
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

DEPENDENCIES = ['wink']

# These are the available sensors mapped to binary_sensor class
SENSOR_TYPES = {
    "opened": "opening",
    "brightness": "light",
    "vibration": "vibration",
    "loudness": "sound",
    "liquid_detected": "moisture",
    "motion": "motion",
    "presence": "occupancy",
    "co_detected": "gas",
    "smoke_detected": "smoke"
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink binary sensor platform."""
    import pywink

    for sensor in pywink.get_sensors():
        if sensor.capability() in SENSOR_TYPES:
            add_devices([WinkBinarySensorDevice(sensor, hass)])

    for key in pywink.get_keys():
        add_devices([WinkBinarySensorDevice(key, hass)])

    for sensor in pywink.get_smoke_and_co_detectors():
        add_devices([WinkBinarySensorDevice(sensor, hass)])

    for hub in pywink.get_hubs():
        add_devices([WinkHub(hub, hass)])


class WinkBinarySensorDevice(WinkDevice, BinarySensorDevice, Entity):
    """Representation of a Wink binary sensor."""

    def __init__(self, wink, hass):
        """Initialize the Wink binary sensor."""
        super().__init__(wink, hass)
        wink = get_component('wink')
        self._unit_of_measurement = self.wink.UNIT
        self.capability = self.wink.capability()

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.capability == "loudness":
            state = self.wink.loudness_boolean()
        elif self.capability == "vibration":
            state = self.wink.vibration_boolean()
        elif self.capability == "brightness":
            state = self.wink.brightness_boolean()
        elif self.capability == "liquid_detected":
            state = self.wink.liquid_boolean()
        elif self.capability == "motion":
            state = self.wink.motion_boolean()
        elif self.capability == "presence":
            state = self.wink.presence_boolean()
        elif self.capability == "co_detected":
            state = self.wink.co_detected_boolean()
        elif self.capability == "smoke_detected":
            state = self.wink.smoke_detected_boolean()
        else:
            state = self.wink.state()

        return state

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return SENSOR_TYPES.get(self.capability)


class WinkHub(WinkDevice, BinarySensorDevice, Entity):
    """Representation of a Wink Hub."""

    def __init(self, wink, hass):
        """Initialize the hub sensor."""
        WinkDevice.__init__(self, wink, hass)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'update needed': self.wink.update_needed(),
            'firmware version': self.wink.firmware_version()
        }

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.wink.state()
