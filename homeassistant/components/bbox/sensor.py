"""Support for Bbox Bouygues Modem Router."""
from datetime import timedelta
import logging

import pybbox
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    DATA_RATE_MEGABITS_PER_SECOND,
    DEVICE_CLASS_TIMESTAMP,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by Bouygues Telecom"

DEFAULT_NAME = "Bbox"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# Sensor types are defined like so: Name, unit, icon
SENSOR_TYPES = {
    "down_max_bandwidth": [
        "Maximum Download Bandwidth",
        DATA_RATE_MEGABITS_PER_SECOND,
        "mdi:download",
    ],
    "up_max_bandwidth": [
        "Maximum Upload Bandwidth",
        DATA_RATE_MEGABITS_PER_SECOND,
        "mdi:upload",
    ],
    "current_down_bandwidth": [
        "Currently Used Download Bandwidth",
        DATA_RATE_MEGABITS_PER_SECOND,
        "mdi:download",
    ],
    "current_up_bandwidth": [
        "Currently Used Upload Bandwidth",
        DATA_RATE_MEGABITS_PER_SECOND,
        "mdi:upload",
    ],
    "uptime": ["Uptime", None, "mdi:clock"],
    "number_of_reboots": ["Number of reboot", None, "mdi:restart"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Bbox sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.
    try:
        bbox_data = BboxData()
        bbox_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config[CONF_NAME]

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        if variable == "uptime":
            sensors.append(BboxUptimeSensor(bbox_data, variable, name))
        else:
            sensors.append(BboxSensor(bbox_data, variable, name))

    add_entities(sensors, True)


class BboxUptimeSensor(SensorEntity):
    """Bbox uptime sensor."""

    def __init__(self, bbox_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.bbox_data = bbox_data
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_TIMESTAMP

    def update(self):
        """Get the latest data from Bbox and update the state."""
        self.bbox_data.update()
        uptime = utcnow() - timedelta(
            seconds=self.bbox_data.router_infos["device"]["uptime"]
        )
        self._state = uptime.replace(microsecond=0).isoformat()


class BboxSensor(SensorEntity):
    """Implementation of a Bbox sensor."""

    def __init__(self, bbox_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.bbox_data = bbox_data
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data from Bbox and update the state."""
        self.bbox_data.update()
        if self.type == "down_max_bandwidth":
            self._state = round(self.bbox_data.data["rx"]["maxBandwidth"] / 1000, 2)
        elif self.type == "up_max_bandwidth":
            self._state = round(self.bbox_data.data["tx"]["maxBandwidth"] / 1000, 2)
        elif self.type == "current_down_bandwidth":
            self._state = round(self.bbox_data.data["rx"]["bandwidth"] / 1000, 2)
        elif self.type == "current_up_bandwidth":
            self._state = round(self.bbox_data.data["tx"]["bandwidth"] / 1000, 2)
        elif self.type == "number_of_reboots":
            self._state = self.bbox_data.router_infos["device"]["numberofboots"]


class BboxData:
    """Get data from the Bbox."""

    def __init__(self):
        """Initialize the data object."""
        self.data = None
        self.router_infos = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Bbox."""

        try:
            box = pybbox.Bbox()
            self.data = box.get_ip_stats()
            self.router_infos = box.get_bbox_info()
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(error)
            self.data = None
            self.router_infos = None
            return False
