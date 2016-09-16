"""
Support for monitoring emoncms feeds.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/sensor.emoncms/
"""
from datetime import timedelta
import logging

import voluptuous as vol
import requests

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_URL, CONF_VALUE_TEMPLATE,
    CONF_UNIT_OF_MEASUREMENT, CONF_ID, CONF_SCAN_INTERVAL,
    STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DECIMALS = 2
CONF_EXCLUDE_FEEDID = "exclude_feed_id"
CONF_ONLY_INCLUDE_FEEDID = "include_only_feed_id"
CONF_SENSOR_NAMES = "sensor_names"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_ID): cv.positive_int,
    vol.Exclusive(CONF_ONLY_INCLUDE_FEEDID, 'only_include_exclude_or_none'):
        vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Exclusive(CONF_EXCLUDE_FEEDID, 'only_include_exclude_or_none'):
        vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Optional(CONF_SENSOR_NAMES):
        vol.All({cv.positive_int: vol.All(cv.string, vol.Length(min=1))}),
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="W"): cv.string,
})

ATTR_SIZE = 'Size'
ATTR_LASTUPDATETIME = 'LastUpdated'
ATTR_TAG = 'Tag'
ATTR_FEEDID = 'FeedId'
ATTR_USERID = 'UserId'
ATTR_FEEDNAME = 'FeedName'
ATTR_LASTUPDATETIMESTR = 'LastUpdatedStr'


def get_id(sensorid, feedtag, feedname, feedid, feeduserid):
    """Return unique identifier for feed / sensor."""
    return "emoncms{}_{}_{}_{}_{}".format(
        sensorid, feedtag, feedname, feedid, feeduserid)


# pylint: disable=too-many-locals
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Emoncms sensor."""
    apikey = config.get(CONF_API_KEY)
    url = config.get(CONF_URL)
    sensorid = config.get(CONF_ID)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    exclude_feeds = config.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = config.get(CONF_ONLY_INCLUDE_FEEDID)
    sensor_names = config.get(CONF_SENSOR_NAMES)
    interval = config.get(CONF_SCAN_INTERVAL)

    data = EmonCmsData(hass, url, apikey, interval)

    data.update()

    if data.data is None:
        return False

    sensors = []

    for elem in data.data:

        if exclude_feeds is not None:
            if int(elem["id"]) in exclude_feeds:
                continue

        if include_only_feeds is not None:
            if int(elem["id"]) not in include_only_feeds:
                continue

        name = None
        if sensor_names is not None:
            name = sensor_names.get(int(elem["id"]), None)

        sensors.append(EmonCmsSensor(hass, data, name, value_template,
                                     unit_of_measurement, str(sensorid),
                                     elem))
    add_devices(sensors)


# pylint: disable=too-many-instance-attributes
class EmonCmsSensor(Entity):
    """Implementation of an EmonCmsSensor sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, data, name, value_template,
                 unit_of_measurement, sensorid, elem):
        """Initialize the sensor."""
        if name is None:
            self._name = "emoncms{}_feedid_{}".format(
                sensorid, elem["id"])
        else:
            self._name = name
        self._identifier = get_id(sensorid, elem["tag"],
                                  elem["name"], elem["id"],
                                  elem["userid"])
        self._hass = hass
        self._data = data
        self._value_template = value_template
        self._unit_of_measurement = unit_of_measurement
        self._sensorid = sensorid
        self._elem = elem

        if self._value_template is not None:
            self._state = template.render_with_possible_json_value(
                self._hass, self._value_template, elem["value"],
                STATE_UNKNOWN)
        else:
            self._state = round(float(elem["value"]), DECIMALS)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the atrributes of the sensor."""
        return {
            ATTR_FEEDID: self._elem["id"],
            ATTR_TAG: self._elem["tag"],
            ATTR_FEEDNAME: self._elem["name"],
            ATTR_SIZE: self._elem["size"],
            ATTR_USERID: self._elem["userid"],
            ATTR_LASTUPDATETIME: self._elem["time"],
            ATTR_LASTUPDATETIMESTR: template.timestamp_local(
                float(self._elem["time"])),
        }

    def update(self):
        """Get the latest data and updates the state."""
        self._data.update()

        if self._data.data is None:
            return

        elem = next((elem for elem in self._data.data
                     if get_id(self._sensorid, elem["tag"],
                               elem["name"], elem["id"],
                               elem["userid"]) == self._identifier),
                    None)

        if elem is None:
            return

        self._elem = elem

        if self._value_template is not None:
            self._state = template.render_with_possible_json_value(
                self._hass, self._value_template, elem["value"],
                STATE_UNKNOWN)
        else:
            self._state = round(float(elem["value"]), DECIMALS)


# pylint: disable=too-few-public-methods
class EmonCmsData(object):
    """The class for handling the data retrieval."""

    def __init__(self, hass, url, apikey, interval):
        """Initialize the data object."""
        self._apikey = apikey
        self._url = "{}/feed/list.json".format(url)
        self._interval = interval
        self._hass = hass
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        try:
            req = requests.get(self._url, params={"apikey": self._apikey},
                               verify=False, allow_redirects=True,
                               timeout=5)
        except requests.exceptions.RequestException as exception:
            _LOGGER.error(exception)
            return
        else:
            if req.status_code == 200:
                self.data = req.json()
            else:
                _LOGGER.error("please verify if the specified config value "
                              "'%s' is correct! (HTTP Status_code = %d)",
                              CONF_URL, req.status_code)
