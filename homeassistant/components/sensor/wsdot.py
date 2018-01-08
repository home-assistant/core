"""
Support for Washington State Department of Transportation (WSDOT) data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.wsdot/
"""
import logging
import re
from datetime import datetime, timezone, timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, ATTR_ATTRIBUTION, CONF_ID
    )
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_TRAVEL_TIMES = 'travel_time'

# API codes for travel time details
ATTR_ACCESS_CODE = 'AccessCode'
ATTR_TRAVEL_TIME_ID = 'TravelTimeID'
ATTR_CURRENT_TIME = 'CurrentTime'
ATTR_AVG_TIME = 'AverageTime'
ATTR_NAME = 'Name'
ATTR_TIME_UPDATED = 'TimeUpdated'
ATTR_DESCRIPTION = 'Description'
ATTRIBUTION = "Data provided by WSDOT"

SCAN_INTERVAL = timedelta(minutes=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_TRAVEL_TIMES): [{
        vol.Required(CONF_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string}]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the WSDOT sensor."""
    sensors = []
    for travel_time in config.get(CONF_TRAVEL_TIMES):
        name = (travel_time.get(CONF_NAME) or
                travel_time.get(CONF_ID))
        sensors.append(
            WashingtonStateTravelTimeSensor(
                name,
                config.get(CONF_API_KEY),
                travel_time.get(CONF_ID)))
    add_devices(sensors, True)


class WashingtonStateTransportSensor(Entity):
    """
    Sensor that reads the WSDOT web API.

    WSDOT provides ferry schedules, toll rates, weather conditions,
    mountain pass conditions, and more. Subclasses of this
    can read them and make them available.
    """

    ICON = 'mdi:car'

    def __init__(self, name, access_code):
        """Initialize the sensor."""
        self._data = {}
        self._access_code = access_code
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON


class WashingtonStateTravelTimeSensor(WashingtonStateTransportSensor):
    """Travel time sensor from WSDOT."""

    RESOURCE = ('http://www.wsdot.wa.gov/Traffic/api/TravelTimes/'
                'TravelTimesREST.svc/GetTravelTimeAsJson')
    ICON = 'mdi:car'

    def __init__(self, name, access_code, travel_time_id):
        """Construct a travel time sensor."""
        self._travel_time_id = travel_time_id
        WashingtonStateTransportSensor.__init__(self, name, access_code)

    def update(self):
        """Get the latest data from WSDOT."""
        params = {ATTR_ACCESS_CODE: self._access_code,
                  ATTR_TRAVEL_TIME_ID: self._travel_time_id}

        response = requests.get(self.RESOURCE, params, timeout=10)
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from WSDOT API")
        else:
            self._data = response.json()
        self._state = self._data.get(ATTR_CURRENT_TIME)

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        if self._data is not None:
            attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
            for key in [ATTR_AVG_TIME, ATTR_NAME, ATTR_DESCRIPTION,
                        ATTR_TRAVEL_TIME_ID]:
                attrs[key] = self._data.get(key)
            attrs[ATTR_TIME_UPDATED] = _parse_wsdot_timestamp(
                self._data.get(ATTR_TIME_UPDATED))
            return attrs

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"


def _parse_wsdot_timestamp(timestamp):
    """Convert WSDOT timestamp to datetime."""
    if not timestamp:
        return None
    # ex: Date(1485040200000-0800)
    milliseconds, tzone = re.search(
        r'Date\((\d+)([+-]\d\d)\d\d\)', timestamp).groups()
    return datetime.fromtimestamp(int(milliseconds) / 1000,
                                  tz=timezone(timedelta(hours=int(tzone))))
