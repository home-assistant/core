"""
homeassistant.components.sensor.bloomsky
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support the sensor of a BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.bloomsky/
"""
import logging
import homeassistant.components.bloomsky as bloomsky
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ["bloomsky"]

# These are the available sensors
SENSOR_TYPES = ["Temperature",
                "Humidity",
                "Rain",
                "Pressure",
                "Luminance",
                "Night",
                "UVIndex"]

# Sensor units - these do not currently align with the API documentation
SENSOR_UNITS = {"Temperature": "°F",
                "Humidity": "%",
                "Pressure": "inHg",
                "Luminance": "cd/m²"}

# Which sensors to format numerically
FORMAT_NUMBERS = ["Temperature", "Pressure"]


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Set up the available BloomSky weather sensors. """

    logger = logging.getLogger(__name__)

    for device_key in bloomsky.BLOOMSKY.devices:
        device = bloomsky.BLOOMSKY.devices[device_key]
        for variable in config["monitored_conditions"]:
            if variable in SENSOR_TYPES:
                add_devices([BloomSkySensor(bloomsky.BLOOMSKY,
                                            device,
                                            variable)])
            else:
                logger.error("Cannot find definition for device: %s", variable)


class BloomSkySensor(Entity):
    """ Represents a single sensor in a BloomSky device. """

    def __init__(self, bs, device, sensor_name):
        self._bloomsky = bs
        self._device_id = device["DeviceID"]
        self._client_name = device["DeviceName"]
        self._sensor_name = sensor_name
        self._state = self.process_state(device)
        self._sensor_update = ""

    @property
    def name(self):
        """ The name of the BloomSky device and this sensor. """
        return "{} {}".format(self._client_name, self._sensor_name)

    @property
    def state(self):
        """ The current state (i.e. value) of this sensor. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ This sensor's units. """
        return SENSOR_UNITS.get(self._sensor_name, None)

    def update(self):
        """ Request an update from the BloomSky API. """
        self._bloomsky.refresh_devices()
        # TS is a Unix epoch timestamp for the last time the BloomSky servers
        # heard from this device. If that value hasn't changed, the value has
        # not been updated.
        last_ts = self._bloomsky.devices[self._device_id]["Data"]["TS"]
        if last_ts != self._sensor_update:
            self.process_state(self._bloomsky.devices[self._device_id])
            self._sensor_update = last_ts

    def process_state(self, device):
        """ Handle the response from the BloomSky API for this sensor. """
        data = device["Data"][self._sensor_name]
        if self._sensor_name == "Rain":
            if data:
                self._state = "Raining"
            else:
                self._state = "Not raining"
        elif self._sensor_name == "Night":
            if data:
                self._state = "Nighttime"
            else:
                self._state = "Daytime"
        elif self._sensor_name in FORMAT_NUMBERS:
            self._state = "{0:.2f}".format(data)
        else:
            self._state = data
