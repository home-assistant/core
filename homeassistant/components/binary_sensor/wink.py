"""
Support for Wink binary sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/binary_sensor.wink/
"""

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor.wink import WinkDevice
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['wink']

# These are the available sensors mapped to binary_sensor class
SENSOR_TYPES = {
    "opened": "opening",
    "brightness": "light",
    "vibration": "vibration",
    "loudness": "sound",
    "noise": "sound",
    "capturing_audio": "sound",
    "liquid_detected": "moisture",
    "motion": "motion",
    "presence": "occupancy",
    "co_detected": "gas",
    "smoke_detected": "smoke",
    "capturing_video": None
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
        add_devices([WinkSmokeDetector(sensor, hass)])

    for hub in pywink.get_hubs():
        add_devices([WinkHub(hub, hass)])

    for remote in pywink.get_remotes():
        add_devices([WinkRemote(remote, hass)])

    for button in pywink.get_buttons():
        add_devices([WinkButton(button, hass)])

    for gang in pywink.get_gangs():
        add_devices([WinkBinarySensorDevice(gang, hass)])

    for door_bell_sensor in pywink.get_door_bells():
        add_devices([WinkBinarySensorDevice(door_bell_sensor, hass)])

     for camera_sensor in pywink.get_cameras():
         try:
             if camera_sensor.capability() in SENSOR_TYPES:
                 add_devices([WinkSensorDevice(camera_sensor)])
         except AttributeError:
             _LOGGER.info("Device isn't a sensor, skipping.")


class WinkBinarySensorDevice(WinkDevice, BinarySensorDevice, Entity):
    """Representation of a Wink binary sensor."""

    def __init__(self, wink, hass):
        """Initialize the Wink binary sensor."""
        super().__init__(wink, hass)
        self._unit_of_measurement = self.wink.unit()
        self.capability = self.wink.capability()

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.wink.state()

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return SENSOR_TYPES.get(self.capability)


class WinkSmokeDetector(WinkDevice, BinarySensorDevice, Entity):
    """Representation of a Wink Smoke detector."""

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'test_activated': self.wink.test_activated()
        }


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


class WinkRemote(WinkDevice, BinarySensorDevice, Entity):
    """Representation of a Wink Lutron Connected bulb remote."""

    def __init(self, wink, hass):
        """Initialize the hub sensor."""
        WinkDevice.__init__(self, wink, hass)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'button_on_pressed': self.wink.button_on_pressed(),
            'button_off_pressed': self.wink.button_off_pressed(),
            'button_up_pressed': self.wink.button_up_pressed(),
            'button_down_pressed': self.wink.button_down_pressed()
        }


class WinkButton(WinkDevice, BinarySensorDevice, Entity):
    """Representation of a Wink Relay button."""

    def __init(self, wink, hass):
        """Initialize the hub sensor."""
        WinkDevice.__init__(self, wink, hass)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'pressed': self.wink.pressed(),
            'long_pressed': self.wink.long_pressed()
        }

