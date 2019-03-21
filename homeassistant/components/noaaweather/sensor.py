"""
Support for US NOAA/National Weather Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.noaaweather/
"""
import datetime
from datetime import timedelta

import logging
import requests

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS, CONF_NAME, LENGTH_METERS, TEMP_CELSIUS,
    TEMP_FAHRENHEIT, LENGTH_KILOMETERS, LENGTH_MILES, LENGTH_INCHES)
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)


ATTR_LAST_UPDATE = 'last_update'
ATTR_SENSOR_ID = 'sensor_id'
ATTR_SITE_ID = 'site_id'
ATTR_SITE_NAME = 'site_name'
CONF_STATIONCODE = 'stationcode'

ATTRIBUTION = "Data provided by National Oceanic "\
                "and Atmospheric Administration"

"""From Met Office, probably not needed"""
CONDITION_CLASSES = {
    'cloudy': ['7', '8'],
    'fog': ['5', '6'],
    'hail': ['19', '20', '21'],
    'lightning': ['30'],
    'lightning-rainy': ['28', '29'],
    'partlycloudy': ['2', '3'],
    'pouring': ['13', '14', '15'],
    'rainy': ['9', '10', '11', '12'],
    'snowy': ['22', '23', '24', '25', '26', '27'],
    'snowy-rainy': ['16', '17', '18'],
    'sunny': ['0', '1'],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}

# Unit mapping
UNIT_MAPPING = {
        'unit:degC': [TEMP_CELSIUS],
        'unit:degF': [TEMP_FAHRENHEIT],
        'unit:degree_(angle)': ['°'],
        'unit:m': [LENGTH_METERS],
        'unit:m_s-1': ['m/s'],
        'unit:Pa': ['Pa'],
        'unit:percent': ['%']
}

DEFAULT_NAME = "NOAA"


MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

# Sensor types are defined like: Name, type of value,
#                       preferred metric units, preferred imperial units
# where type is one of:
#   single - single value, for example textDescription or presentWeather
#   measurement - single measurement as a dictionary of attributes
#                   'unitCode' and 'value' attributes expected
#   array - array of dictionaries.  At this point only case seen
#           is for cloudLayers, with the items 'base':['value','unitCode']
#           and 'amount'

SENSOR_TYPES = {
    'textDescription': ['Weather', 'single', None, None],
    'presentWeather': ['Present Weather', 'single', None, None],
    'temperature': ['Temperature', 'measurement',
                    TEMP_CELSIUS, TEMP_FAHRENHEIT],
    'dewpoint': ['dewpoint', 'measurement',
                 TEMP_CELSIUS, TEMP_FAHRENHEIT],
    'windChill': ['Wind Chill', 'measurement',
                  TEMP_CELSIUS, TEMP_FAHRENHEIT],
    'heatIndex': ['Heat Index', 'measurement',
                  TEMP_CELSIUS, TEMP_FAHRENHEIT],
    'windSpeed': ['Wind Speed', 'measurement',
                  'm/s', 'mph'],
    'windDirection': ['Wind Bearing', 'measurement',
                      '°', '°'],
    'windGust': ['Wind Gust', 'measurement',
                 'm/s', 'mph'],
    'barometricPressure': ['Pressure', 'measurement', 'mbar', 'mbar'],
    'seaLevelPressure': ['Sea Level Pressure', 'measurement',
                         'mbar', 'mbar'],
    'maxTemperatureLast24Hours': ['Maximum Temperature last 24 Hours',
                                  'measurement', TEMP_CELSIUS,
                                  TEMP_FAHRENHEIT],
    'minTemperatureLast24Hours': ['Minimum Temperature last 24 Hours',
                                  'measurement', TEMP_CELSIUS,
                                  TEMP_FAHRENHEIT],
    'precipitationLastHour': ['Precipitation in last hour', 'measurement',
                              'mm', LENGTH_INCHES],
    'precipitationLast3Hours': ['Precipitation in last 3 hours',
                                'measurement', 'mm', LENGTH_INCHES],
    'precipitationLast6Hours': ['Precipitation in last 6 hours',
                                'measurement', 'mm', LENGTH_INCHES],
    'relativeHumidity': ['Humidity', 'measurement', 'humidity',
                         '%', '%'],
    'cloudLayers': ['Cloud Layers', 'array', None, None],
    'visibility': ['Visibility', 'measurement',
                   LENGTH_KILOMETERS, LENGTH_MILES]
}

SENSOR_TYPES_SET = set(SENSOR_TYPES)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_STATIONCODE): cv.string,

})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NOAA sensor platform."""
    #
    # The key item is the location to use,
    # which can be configured by specifying longitude and latitude.
    # If these are not set in the component configuration, the
    # longitude and latitude specified in the overall home assistant
    # configuration are used.
    # Optionally the station code for the observation station, can
    # be specified. This must be one which is in the station list
    # for the location provided.  If no station code is configured,
    # the closest station is chosen.
    #
    name = config.get(CONF_NAME)        # Get name (or default)
    # Get configured stationcode
    confstationcode = config.get(CONF_STATIONCODE)
    #
    # Get latitude and longitude. These may come from the component
    # configuration, or if not given there, from the overall home assistant
    # configuration.
    #
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    # If we get here without the required configuration items, log an error.

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return
    #
    # Get metadata about the location using the /points/ function
    # This checks that the location is within the NWS coverage area.
    #
    try:
        locmetadata = requests.get(
            'https://api.weather.gov/points/{},{}'.format(
                latitude, longitude))
    except Exception:
        _LOGGER.error("Error getting metadata for location %s,%s",
                      latitude, longitude)
        return

    if locmetadata.status_code != 200:
        _LOGGER.error("Error getting metadata for location %s,%s, status=%s",
                      latitude, longitude, locmetadata.status_code)
        return
    #
    # The key metadata we need are:
    #   observationStations - URL to get list of observation stations
    #   forecast - URL to get semi-daily forecast
    #   forecastHourly - URL to get hourly forecast
    #
    try:
        obsstaurl = locmetadata.json()['properties']['observationStations']
    except Exception:
        _LOGGER.error("No observations URL for location %s,%s",
                      latitude, longitude)
        return

    try:
        forecasturl = locmetadata.json()['properties']['forecast']
    except Exception:
        _LOGGER.error("No forecast URL for location %s,%s",
                      latitude, longitude)
        return

    try:
        forecasthourlyurl = locmetadata.json()['properties']['forecastHourly']
    except Exception:
        _LOGGER.error("No hourly forecast URL for location %s,%s",
                      latitude, longitude)
        return

    #
    # Get list of stations from the /gridpoints/.../stations function
    # If no station was configured, use first station from list as the
    # station for observations.  If a station was configured, verify
    # that it is in the list for this location.
    #
    stationlist = requests.get(obsstaurl)
    if stationlist.status_code != 200:
        _LOGGER.error("Cannot get station list for location %s,%s",
                      latitude, longitude)
        return
    #
    # Do we have a station from the configuration?
    #

    stationcode = None

    #
    # loop through list of stations to check if code is valid station
    # for this location
    #
    for station in stationlist.json()['features']:
        if confstationcode is None:
            stationcode = station['properties']['stationIdentifier']
            break
        else:
            if confstationcode == station['properties']['stationIdentifier']:
                stationcode = confstationcode
                break
    #
    # Did we find a valid station?
    #
    if stationcode is None:
        if confstationcode is None:
            _LOGGER.error("No stations returned for location %s,%s",
                          latitude, longitude)
        else:
            _LOGGER.error("Station %s not found in list for location %s,%s",
                          confstationcode, latitude, longitude)

    #
    # Get station meta data
    #
    try:
        stationmeta = requests.get('https://api.weather.gov/stations/{}'
                                   .format(stationcode))
    except Exception:
        _LOGGER.error("Can't get station metadata for station %s",
                      stationcode)
    if stationmeta.status_code != 200:
        _LOGGER.error("Can't get station metadata for station %s, status %s",
                      stationcode, stationmeta.status_code)
    #
    # Get station information
    #
    stationid = stationmeta.json()['properties']['stationIdentifier']
    stationname = stationmeta.json()['properties']['name']

    #
    # Create the data object for observations for this location/station.
    #

    noaadata = NOAACurrentData(hass, stationcode,
                               stationid, stationname,
                               forecasturl, forecasthourlyurl, name)
    #
    # Perform a data update to get first set of data and available
    # measurements
    #
    noaadata.update()
    if None in noaadata.data:
        return

    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(NOAACurrentSensor(hass, noaadata, variable, name))

    add_entities(sensors, True)


class NOAACurrentSensor(Entity):
    """Implementation of a NOAA station current sensor."""

    def __init__(self, hass, noaadata, condition, name):
        """Initialize the sensor."""
        self._condition = condition
        self.noaadata = noaadata
        self._name = name
        # Set whether desired units are metric (default) or
        # imperial.
        if hass.config.units == METRIC_SYSTEM:
            self.desiredunit = SENSOR_TYPES[condition][2]
        elif hass.config.units == IMPERIAL_SYSTEM:
            self.desiredunit = SENSOR_TYPES[condition][3]
        else:
            _LOGGER.warning("Unknown unit system %s, defaulting to metric",
                            hass.config.units)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug("Getting state for %s", self._condition)
        _LOGGER.debug("noaadata.data set is %s", set(self.noaadata.data))
        #
        # ensure we have some data
        #
        if self._condition in self.noaadata.data:
            variable = self.noaadata.data[self._condition]
            _LOGGER.debug("Condition value=%s", variable)
            #
            # Now check for type of value for this attribute
            #
            if SENSOR_TYPES[self._condition][1] == 'single':
                # attribute itself is the value for single value items
                _LOGGER.debug("Condition %s is single value='%s'",
                              self._condition, variable)
                return variable
            elif SENSOR_TYPES[self._condition][1] == 'measurement':
                # value attribute of variable for measurements
                _LOGGER.debug("Condition %s is measurement='%s',\
                               from string '%s'",
                              self._condition, variable['value'], variable)
                if variable['value'] is None:
                    return None

                res = variable['value']
                # Check if we need to change units
                if 'unitCode' in variable:
                    if not variable['unitCode'] in UNIT_MAPPING:
                        _LOGGER.debug("No translation for unitCode %s",
                                      variable['unitCode'])
                        self.desiredunit = None
                        return res
                    #
                    # We have a unit mapping to use
                    #
                    srcunit = UNIT_MAPPING[variable['unitCode']][0]
                    _LOGGER.debug("srcunit=%s, desiredunit=%s", srcunit,
                                  self.desiredunit)
                    if srcunit != self.desiredunit:
                        # need to conver units, identify conversion required
                        if srcunit == TEMP_CELSIUS and \
                                self.desiredunit == TEMP_FAHRENHEIT:
                            res = res * 9 / 5 + 32
                        elif srcunit == TEMP_FAHRENHEIT and \
                                self.desiredunit == TEMP_CELSIUS:
                            res = (res - 32) * 5 / 9
                        elif srcunit == LENGTH_METERS:
                            if self.desiredunit == LENGTH_MILES:
                                res = res / 1609.344
                            elif self.desiredunit == LENGTH_KILOMETERS:
                                res = res / 1000
                            elif self.desiredunit == 'mm':
                                res = res * 1000
                            elif self.desiredunit == LENGTH_INCHES:
                                res = res * 39.37007874
                        elif srcunit == 'Pa' and \
                                self.desiredunit == 'mbar':
                            res = res / 100
                        elif srcunit == 'm/s' and \
                                self.desiredunit == 'mph':
                            res = res * 2.236936292
                return round(res, 1)

            elif SENSOR_TYPES[self._condition][1] == 'array':
                # We only know how to handle cloudLayers
                if self._condition == 'cloudLayers':
                    #
                    # The array for cloudLayers includes a height and
                    # text for each layer.  At this point we will
                    # only deal with the text for the first layer (if anY) and
                    # ignore the other values.
                    if variable:
                        return variable[0]['amount']
                    else:
                        return None
            elif SENSOR_TYPE[self._condition][1] is not None:
                # We only get here if the type of value is something we don't
                # understand
                #
                _LOGGER.debug("No value type for condition %s",
                              self._condition)
            return None
        #
        # No data
        #
        _LOGGER.debug("No data for condition %s", self._condition)
        #
        # If we get here then we had a condition that was in the first data
        # we got when setting up, but is not being returned now.
        # Just return a null value, so the state will go to unknown.
        #
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        attr[ATTR_LAST_UPDATE] = self.noaadata.lastupdate
        attr[ATTR_SITE_ID] = self.noaadata.stationid
        attr[ATTR_SITE_NAME] = self.noaadata.stationname
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measure for the sensor."""
        #
        # ensure we have some data
        #
        if self._condition in self.noaadata.data:
            variable = self.noaadata.data[self._condition]
            #
            # Now check for type of value for this attribute
            # Only measurements have units
            #
            if SENSOR_TYPES[self._condition][1] == 'measurement':
                # We should have a unitCode supplied from the API response.
                if self.desiredunit is not None:
                    return self.desiredunit

                if 'unitCode' in variable:
                    # run it through our mapping table.  If it
                    # doesn't have a map, return the value we recevied.
                    if variable['unitCode'] in UNIT_MAPPING:
                        return UNIT_MAPPING[variable['unitCode']][0]
                    else:
                        return variable['unitCode']
        return None

    #
    # Handle data update request
    #
    def update(self):
        """Update the sensor data."""
        self.noaadata.update()


#
# class to obtain the data from the NOAA/NWS API
#
class NOAACurrentData(Entity):
    """Get the latest data from NOAA API."""

    def __init__(self, hass, stationcode,
                 stationid, stationname, forecasturl, forecasthourlyurl, name):
        """Initialize the current data object."""
        _LOGGER.debug("Initialize NOAACurrentData with stationcode=%s, \
                       stationid='%s',stationname='%s',forecasturl='%s',\
                       forecasthourlyurl='%s',name='%s'",
                      stationcode, stationid, stationname,
                      forecasturl, forecasthourlyurl, name)

        self.stationcode = stationcode
        self.stationid = stationid
        self.stationname = stationname
        self.forecasturl = forecasturl
        self.forecasthourlyurl = forecasthourlyurl
        self.obsurl = "https://api.weather.gov/stations/{}"\
            "/observations/latest".format(stationcode)

        self._name = name
        self.lastupdate = datetime.datetime.now(datetime.timezone.utc)
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest observation data from the station."""
        #
        # Log that we were called
        #
        _LOGGER.debug("update called for station %s", self.stationcode)

        try:
            obslist = requests.get(self.obsurl)
        except Exception:
            _LOGGER.error("Cannot get observations for station %s",
                          self.stationcode)
        #
        # Make sure good status result
        #
        if obslist.status_code != 200:
            _LOGGER.error("Cannot get observations for station %s, status=%s",
                          self.stationcode, obslist.status_code)
        #
        # Get the timestamp of the report, if any
        #
        if 'timestamp' in obslist.json()['properties']:
            tsstring = obslist.json()['properties']['timestamp']
            self.lastupdate = datetime.datetime.strptime(
                '{}{}'.format(tsstring[0:22], tsstring[23:25]),
                '%Y-%m-%dT%H:%M:%S%z')
        _LOGGER.debug("timestamp=%s, obslist properties='%s'",
                      self.lastupdate, obslist.json()['properties'])

        #
        # Now loop through all observation values returned and set the
        # condition value
        #
        _LOGGER.debug("checking for variables using set %s intersection \
                       set %s which is '%s'",
                      SENSOR_TYPES_SET, set(obslist.json()['properties']),
                      SENSOR_TYPES_SET.intersection(set(obslist.json()
                                                        ['properties'])))

        for variable in SENSOR_TYPES_SET.intersection(
                set(obslist.json()['properties'])):
            _LOGGER.debug("setting value variable=%s, value='%s'",
                          variable, obslist.json()['properties'][variable])
            self.data[variable] = obslist.json()['properties'][variable]
