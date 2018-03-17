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
    CONF_API_KEY, CONF_URL, CONF_VALUE_TEMPLATE, CONF_UNIT_OF_MEASUREMENT,
    CONF_ID, CONF_SCAN_INTERVAL, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_FEEDID = 'FeedId'
ATTR_FEEDNAME = 'FeedName'
ATTR_LASTUPDATETIME = 'LastUpdated'
ATTR_LASTUPDATETIMESTR = 'LastUpdatedStr'
ATTR_SIZE = 'Size'
ATTR_TAG = 'Tag'
ATTR_USERID = 'UserId'

CONF_EXCLUDE_FEEDID = 'exclude_feed_id'
CONF_ONLY_INCLUDE_FEEDID = 'include_only_feed_id'
CONF_SENSOR_NAMES = 'sensor_names'

DECIMALS = 2
DEFAULT_UNIT = 'W'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

ONLY_INCL_EXCL_NONE = 'only_include_exclude_or_none'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_ID): cv.positive_int,
    vol.Exclusive(CONF_ONLY_INCLUDE_FEEDID, ONLY_INCL_EXCL_NONE):
        vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Exclusive(CONF_EXCLUDE_FEEDID, ONLY_INCL_EXCL_NONE):
        vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Optional(CONF_SENSOR_NAMES):
        vol.All({cv.positive_int: vol.All(cv.string, vol.Length(min=1))}),
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_UNIT): cv.string,
})


def get_id(sensorid, feedtag, feedname, feedid, feeduserid):
    """Return unique identifier for feed / sensor."""
    return "emoncms{}_{}_{}_{}_{}".format(
        sensorid, feedtag, feedname, feedid, feeduserid)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Emoncms sensor."""
    apikey = config.get(CONF_API_KEY)
    url = config.get(CONF_URL)
    sensorid = config.get(CONF_ID)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    exclude_feeds = config.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = config.get(CONF_ONLY_INCLUDE_FEEDID)
    sensor_names = config.get(CONF_SENSOR_NAMES)
    interval = config.get(CONF_SCAN_INTERVAL)

    if value_template is not None:
        value_template.hass = hass

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


class EmonCmsSensor(Entity):
    """Implementation of an Emoncms sensor."""

    def __init__(self, hass, data, name, value_template,
                 unit_of_measurement, sensorid, elem):
        """Initialize the sensor."""
        if name is None:
            # Suppress ID in sensor name if it's 1, since most people won't
            # have more than one EmonCMS source and it's redundant to show the
            # ID if there's only one.
            id_for_name = '' if str(sensorid) == '1' else sensorid
            # Use the feed name assigned in EmonCMS or fall back to the feed ID
            feed_name = elem.get('name') or 'Feed {}'.format(elem['id'])
            self._name = "EmonCMS{} {}".format(id_for_name, feed_name)
        else:
            self._name = name
        self._identifier = get_id(
            sensorid, elem["tag"], elem["name"], elem["id"], elem["userid"])
        self._hass = hass
        self._data = data
        self._value_template = value_template
        self._unit_of_measurement = unit_of_measurement
        self._sensorid = sensorid
        self._elem = elem

        if self._value_template is not None:
            self._state = self._value_template.render_with_possible_json_value(
                elem["value"], STATE_UNKNOWN)
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
        """Return the attributes of the sensor."""
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
            self._state = self._value_template.render_with_possible_json_value(
                elem["value"], STATE_UNKNOWN)
        else:
            self._state = round(float(elem["value"]), DECIMALS)


class EmonCmsData(object):
    """The class for handling the data retrieval."""

    def __init__(self, hass, url, apikey, interval):
        """Initialize the data object."""
        self._apikey = apikey
        self._url = '{}/feed/list.json'.format(url)
        self._interval = interval
        self._hass = hass
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Emoncms."""
        try:
            parameters = {"apikey": self._apikey}
            req = requests.get(
                self._url, params=parameters, allow_redirects=True, timeout=5)
        except requests.exceptions.RequestException as exception:
            _LOGGER.error(exception)
            return
        else:
            if req.status_code == 200:
                self.data = req.json()
            else:
                _LOGGER.error("Please verify if the specified config value "
                              "'%s' is correct! (HTTP Status_code = %d)",
                              CONF_URL, req.status_code)
