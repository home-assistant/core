"""
Support for the Netatmo binary sensors.

The binary sensors based on events seen by the Netatmo cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.netatmo/.
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.netatmo import CameraData
from homeassistant.loader import get_component
from homeassistant.const import CONF_TIMEOUT, CONF_OFFSET
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['netatmo']

# These are the available sensors mapped to binary_sensor class
WELCOME_SENSOR_TYPES = {
    "Someone known": "motion",
    "Someone unknown": "motion",
    "Motion": "motion",
}
PRESENCE_SENSOR_TYPES = {
    "Outdoor motion": "motion",
    "Outdoor human": "motion",
    "Outdoor animal": "motion",
    "Outdoor vehicle": "motion"
}
TAG_SENSOR_TYPES = {
    "Tag Vibration": "vibration",
    "Tag Open": "opening"
}

CONF_HOME = 'home'
CONF_CAMERAS = 'cameras'
CONF_WELCOME_SENSORS = 'welcome_sensors'
CONF_PRESENCE_SENSORS = 'presence_sensors'
CONF_TAG_SENSORS = 'tag_sensors'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOME): cv.string,
    vol.Optional(CONF_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_OFFSET): cv.positive_int,
    vol.Optional(CONF_CAMERAS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(
        CONF_WELCOME_SENSORS, default=WELCOME_SENSOR_TYPES.keys()):
        vol.All(cv.ensure_list, [vol.In(WELCOME_SENSOR_TYPES)]),
    vol.Optional(
        CONF_PRESENCE_SENSORS, default=PRESENCE_SENSOR_TYPES.keys()):
        vol.All(cv.ensure_list, [vol.In(PRESENCE_SENSOR_TYPES)]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the access to Netatmo binary sensor."""
    netatmo = get_component('netatmo')
    home = config.get(CONF_HOME, None)
    timeout = config.get(CONF_TIMEOUT, 15)
    offset = config.get(CONF_OFFSET, 90)

    module_name = None

    import lnetatmo
    try:
        data = CameraData(netatmo.NETATMO_AUTH, home)
        if data.get_camera_names() == []:
            return None
    except lnetatmo.NoDevice:
        return None

    welcome_sensors = config.get(
        CONF_WELCOME_SENSORS, WELCOME_SENSOR_TYPES)
    presence_sensors = config.get(
        CONF_PRESENCE_SENSORS, PRESENCE_SENSOR_TYPES)
    tag_sensors = config.get(CONF_TAG_SENSORS, TAG_SENSOR_TYPES)

    for camera_name in data.get_camera_names():
        camera_type = data.get_camera_type(camera=camera_name, home=home)
        if camera_type == 'NACamera':
            if CONF_CAMERAS in config:
                if config[CONF_CAMERAS] != [] and \
                   camera_name not in config[CONF_CAMERAS]:
                    continue
            for variable in welcome_sensors:
                add_devices([NetatmoBinarySensor(
                    data, camera_name, module_name, home, timeout,
                    offset, camera_type, variable)])
        if camera_type == 'NOC':
            if CONF_CAMERAS in config:
                if config[CONF_CAMERAS] != [] and \
                   camera_name not in config[CONF_CAMERAS]:
                    continue
            for variable in presence_sensors:
                add_devices([NetatmoBinarySensor(
                    data, camera_name, module_name, home, timeout, offset,
                    camera_type, variable)])

        for module_name in data.get_module_names(camera_name):
            for variable in tag_sensors:
                camera_type = None
                add_devices([NetatmoBinarySensor(
                    data, camera_name, module_name, home, timeout, offset,
                    camera_type, variable)])


class NetatmoBinarySensor(BinarySensorDevice):
    """Represent a single binary sensor in a Netatmo Camera device."""

    def __init__(self, data, camera_name, module_name, home,
                 timeout, offset, camera_type, sensor):
        """Set up for access to the Netatmo camera events."""
        self._data = data
        self._camera_name = camera_name
        self._module_name = module_name
        self._home = home
        self._timeout = timeout
        self._offset = offset
        if home:
            self._name = '{} / {}'.format(home, camera_name)
        else:
            self._name = camera_name
        if module_name:
            self._name += ' / ' + module_name
        self._sensor_name = sensor
        self._name += ' ' + sensor
        camera_id = data.camera_data.cameraByName(
            camera=camera_name, home=home)['id']
        self._unique_id = "Netatmo_binary_sensor {0} - {1}".format(
            self._name, camera_id)
        self._cameratype = camera_type
        self.update()

    @property
    def name(self):
        """Return the name of the Netatmo device and this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        if self._cameratype == 'NACamera':
            return WELCOME_SENSOR_TYPES.get(self._sensor_name)
        elif self._cameratype == 'NOC':
            return PRESENCE_SENSOR_TYPES.get(self._sensor_name)
        else:
            return TAG_SENSOR_TYPES.get(self._sensor_name)

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return self._state

    def update(self):
        """Request an update from the Netatmo API."""
        self._data.update()
        self._data.update_event()

        if self._cameratype == 'NACamera':
            if self._sensor_name == "Someone known":
                self._state =\
                    self._data.camera_data.someoneKnownSeen(
                        self._home, self._camera_name, self._timeout*60)
            elif self._sensor_name == "Someone unknown":
                self._state =\
                    self._data.camera_data.someoneUnknownSeen(
                        self._home, self._camera_name, self._timeout*60)
            elif self._sensor_name == "Motion":
                self._state =\
                    self._data.camera_data.motionDetected(
                        self._home, self._camera_name, self._timeout*60)
        elif self._cameratype == 'NOC':
            if self._sensor_name == "Outdoor motion":
                self._state =\
                    self._data.camera_data.outdoormotionDetected(
                        self._home, self._camera_name, self._offset)
            elif self._sensor_name == "Outdoor human":
                self._state =\
                    self._data.camera_data.humanDetected(
                        self._home, self._camera_name, self._offset)
            elif self._sensor_name == "Outdoor animal":
                self._state =\
                    self._data.camera_data.animalDetected(
                        self._home, self._camera_name, self._offset)
            elif self._sensor_name == "Outdoor vehicle":
                self._state =\
                    self._data.camera_data.carDetected(
                        self._home, self._camera_name, self._offset)
        if self._sensor_name == "Tag Vibration":
            self._state =\
                self._data.camera_data.moduleMotionDetected(
                    self._home, self._module_name, self._camera_name,
                    self._timeout*60)
        elif self._sensor_name == "Tag Open":
            self._state =\
                self._data.camera_data.moduleOpened(
                    self._home, self._module_name, self._camera_name)
        else:
            return None
