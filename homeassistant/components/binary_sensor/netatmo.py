"""
Support for the Netatmo binary sensors.

The binary sensors based on events seen by the NetatmoCamera

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.netatmo/
"""
import logging
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.netatmo import WelcomeData
from homeassistant.loader import get_component
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ["netatmo"]

_LOGGER = logging.getLogger(__name__)


# These are the available sensors mapped to binary_sensor class
SENSOR_TYPES = {
    "Someone known": "motion",
    "Someone unknown": "motion",
    "Motion": "motion",
}

CONF_HOME = 'home'
CONF_CAMERAS = 'cameras'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOME): cv.string,
    vol.Optional(CONF_CAMERAS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_TYPES.keys()):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup access to Netatmo binary sensor."""
    netatmo = get_component('netatmo')
    home = config.get(CONF_HOME, None)

    import lnetatmo
    try:
        data = WelcomeData(netatmo.NETATMO_AUTH, home)
    except lnetatmo.NoDevice:
        return None

    if data.get_camera_names() == []:
        return None

    sensors = config.get(CONF_MONITORED_CONDITIONS, SENSOR_TYPES)

    for camera_name in data.get_camera_names():
        if CONF_CAMERAS in config:
            if config[CONF_CAMERAS] != [] and \
               camera_name not in config[CONF_CAMERAS]:
                continue
        for variable in sensors:
            add_devices([WelcomeBinarySensor(data, camera_name, home,
                                             variable)])


class WelcomeBinarySensor(BinarySensorDevice):
    """Represent a single binary sensor in a Netatmo Welcome device."""

    def __init__(self, data, camera_name, home, sensor):
        """Setup for access to the Netatmo camera events."""
        self._data = data
        self._camera_name = camera_name
        self._home = home
        if home:
            self._name = home + ' / ' + camera_name
        else:
            self._name = camera_name
        self._sensor_name = sensor
        self._name += ' ' + sensor
        camera_id = data.welcomedata.cameraByName(camera=camera_name,
                                                  home=home)['id']
        self._unique_id = "Welcome_binary_sensor {0} - {1}".format(self._name,
                                                                   camera_id)
        self.update()

    @property
    def name(self):
        """The name of the Netatmo device and this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return SENSOR_TYPES.get(self._sensor_name)

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return self._state

    def update(self):
        """Request an update from the Netatmo API."""
        self._data.update()
        self._data.welcomedata.updateEvent(home=self._data.home)

        if self._sensor_name == "Someone known":
            self._state =\
                    self._data.welcomedata.someoneKnownSeen(self._home,
                                                            self._camera_name)
        elif self._sensor_name == "Someone unknown":
            self._state =\
                self._data.welcomedata.someoneUnknownSeen(self._home,
                                                          self._camera_name)
        elif self._sensor_name == "Motion":
            self._state =\
                self._data.welcomedata.motionDetected(self._home,
                                                      self._camera_name)
        else:
            return None
