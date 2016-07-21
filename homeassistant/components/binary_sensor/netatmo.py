"""
Support for the Netatmo Welcome camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.netatmo/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.util import Throttle
from homeassistant.components.binary_sensor import BinarySensorDevice, PLATFORM_SCHEMA
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

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup access to Netatmo Welcome cameras."""
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
        if config[CONF_CAMERAS] != []:
            if camera_name not in config[CONF_CAMERAS]:
                continue
        for variable in sensors:
            add_devices([WelcomeBinarySensor(data, camera_name, home,
                         variable)])

class WelcomeBinarySensor(BinarySensorDevice):
    """Represent a single binary sensor in a Netatmo Welcome device."""

    def __init__(self, data, camera_name, home, sensor):
        self._data = data
        self._camera_name = camera_name
        self._home = home
        if home:
            self._name = home + ' / ' + camera_name
        else:
            self._name = camera_name
        self._sensor_name = sensor
        self._name += ' ' + sensor
        self._unique_id = "Welcome_binary_sensor {}".format(self._name)
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
        """Request an update from the Netatmo API"""
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


class WelcomeData(object):
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, home=None):
        """Initialize the data object."""
        self.auth = auth
        self.welcomedata = None
        self.camera_names = []
        self.home = home

    def get_camera_names(self):
        """Return all module available on the API as a list."""
        self.camera_names = []
        self.update()
        if not self.home:
            for home in self.welcomedata.cameras:
                for camera in self.welcomedata.cameras[home].values():
                    self.camera_names.append(camera['name'])
        else:
            for camera in self.welcomedata.cameras[self.home].values():
                self.camera_names.append(camera['name'])
        return self.camera_names

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the NetAtmo API to update the data."""
        import lnetatmo
        self.welcomedata = lnetatmo.WelcomeData(self.auth)
