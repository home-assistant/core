"""
Support for monitoring OctoPrint binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.octoprint/
"""
import logging
import requests

from homeassistant.const import CONF_NAME, STATE_ON, STATE_OFF
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.loader import get_component

DEPENDENCIES = ["octoprint"]

SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    "Printing": ["printer", "state", "printing", None],
    "Printing Error": ["printer", "state", "error", None]
}

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available OctoPrint binary sensors."""
    octoprint = get_component('octoprint')
    name = config.get(CONF_NAME, "OctoPrint")
    monitored_conditions = config.get("monitored_conditions",
                                      SENSOR_TYPES.keys())

    devices = []
    for octo_type in monitored_conditions:
        if octo_type in SENSOR_TYPES:
            new_sensor = OctoPrintBinarySensor(octoprint.OCTOPRINT,
                                               octo_type,
                                               SENSOR_TYPES[octo_type][2],
                                               name,
                                               SENSOR_TYPES[octo_type][3],
                                               SENSOR_TYPES[octo_type][0],
                                               SENSOR_TYPES[octo_type][1],
                                               "flags")
            devices.append(new_sensor)
        else:
            _LOGGER.error("Unknown OctoPrint sensor type: %s", octo_type)
    add_devices(devices)


# pylint: disable=too-many-instance-attributes
class OctoPrintBinarySensor(BinarySensorDevice):
    """Representation an OctoPrint binary sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, api, condition, sensor_type, sensor_name,
                 unit, endpoint, group, tool=None):
        """Initialize a new OctoPrint sensor."""
        self.sensor_name = sensor_name
        if tool is None:
            self._name = sensor_name + ' ' + condition
        else:
            self._name = sensor_name + ' ' + condition
        self.sensor_type = sensor_type
        self.api = api
        self._state = False
        self._unit_of_measurement = unit
        self.api_endpoint = endpoint
        self.api_group = group
        self.api_tool = tool
        # Set initial state
        self.update()
        _LOGGER.debug("Created OctoPrint binary sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.is_on

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        if self._state:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return None

    def update(self):
        """Update state of sensor."""
        try:
            self._state = self.api.update(self.sensor_type,
                                          self.api_endpoint,
                                          self.api_group,
                                          self.api_tool)
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            return

        if self._state is None:
            _LOGGER.warning("Unable to locate value for %s", self.sensor_type)
