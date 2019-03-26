"""
Support for US NOAA/National Weather Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.noaaweather/

This component gets data from the US NOAA/National Weather Service API.
Documentation on the API is at
https://www.weather.gov/documentation/services-web-api

Configuration:
  - platform: noaaweather
    name: <string>          # name for the platform instance (defaults to
                            # "NOAA Weather"
    latitude = <number>     # latitude for the location, defaults to
                            # homeassistant latitude configuration value
    longitude = <number>    # longitude for the location, defaults to
                            # homeassistant longitude configure value
                            # Note that latitude and longitude are rounded
                            # to 4 decimal places, since that is what
                            # the NOAA/NWS API accepts.
    stationcode = <string>  # NOAA/NWS weather reporting station
                            # to use for conditions source.  Note that this
                            # must be one that NOAA/NWS considers
                            # as near the location provided.
                            # If it is not provided, the closest
                            # station to the location is used. Choices
                            # can be found by going to the normal forecast
                            # web page for the location and then using the
                            # "More Local Wx" link.   The station codes are
                            # part of the URL for each location shown:
                            # the uppercase letters just before the .html
                            # suffix are the station codes.
    monitored_conditions:   # list of conditions to get.  At least one is
                            # required. The complete condition list is:
        - temperature       # temperature in degrees Celsius or Fahrenheit
        - textDescription   # single word description of weather condition
        - dewpoint          # dewpoint in degress Celsius or Fahrenheit
        - windChill         # wind chill temperature in degrees C or F
        - windSpeed         # sustained wind speed in m/s or mph
        - windDirection     # direction of sustained winds (degrees angle)
        - windGust          # speed of wind gusts in m/s or mph
        - heatIndex         # heat index temperature in degrees C of F
        - barometricPressure    # pressure in mbar
        - seaLevelPressure      # current sea level pressure in mbar
        - precipitationLastHour # liquid precipitation in last hour (mm or in)
        - precipitationLast3Hours # liquid precipitation in last 3 hours (mm
                                # or in). Note that this is only returned
                                # on three hour intervals, and only when
                                # there has been some liquid precipitation
                                # in that time. It is not normally useful.
        - precipitationLast6Hours # liquid precipitation in last 6 hours (mm
                                # or in). Note that this is only returned
                                # on six hour intervals, and only when
                                # there has been some liquid precipitation
                                # in that time. It is not normally useful.
        - relativeHumidity      # relative humidity in percent
        - visibility            # visibility in km or miles.
        - cloudLayers           # Three character abbreviation for the
                                # type of the lowest cloud layer. Note
                                # that the data returned from NOAA/NWS
                                # actually includes information for multiple
                                # cloud layers, including the elevation of
                                # the layer, but at this point only
                                # the description of the first layer is
                                # recorded.
        - minTemperatureLast24Hours # Minimum temperature in the last 24 hours
                                # in degrees C or F.  This is only reported
                                # once per day, so it is not really useful.
        - maxTemperatureLast24Hours # Maximum temperature in the last 24 hours
                                # in degrees C or F.  This is only reported
                                # once per day, so it is not really useful.

Some notes on the data returned from NOAA/NWS:
Not all stations have the equipment to measure all of the conditions.
In addition, an empty or null value is returned by the station for some
conditions in certain states:  for example, when the air is calm, windSpeed
will return null instead of zero.  As the station retures a null value when
it does not have the equipment for the measurement as well, there is no
way to determine whether the station can measure the condition, but just not
now, or if it will never return a measurement for that condition.

Also, some stations may return all null values for a given request.



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
from homeassistant.exceptions import (
    ConfigEntryNotReady, PlatformNotReady)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NOAA Weather"

#
# The rates at which new measurement values appear varies by station.
# Typically the measurements from airport weather stations will only update
# once an hour, while other stations may update much more frequently.
# To avoid having the NWS update cycle and polling mismatch (poll just
# before the update) by an hour, we will allow more frequent
# requests.
#
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
SCAN_INTERVAL = timedelta(minutes=30)

REQUESTS_HEADERS = {'user-agent':
                    "Home Assistant component noaaweather sensor v0.1",
                    'Accept': 'application/geo+json'}

ATTR_LAST_UPDATE = 'last_update'
ATTR_SENSOR_ID = 'sensor_id'
ATTR_SITE_ID = 'site_id'
ATTR_SITE_NAME = 'site_name'
CONF_STATIONCODE = 'stationcode'

ATTRIBUTION = "Data provided by National Oceanic "\
                "and Atmospheric Administration"


# Unit mapping table
# The NWS API returns a unit of measure value with each
# numerical value in the format "unit:<unitname>".
# The units in this table are the only ones
# returned at this time, except that unit:degF is
# not currently returned.
#
UNIT_MAPPING = {
        'unit:degC': [TEMP_CELSIUS],
        'unit:degF': [TEMP_FAHRENHEIT],
        'unit:degree_(angle)': ['°'],
        'unit:m': [LENGTH_METERS],
        'unit:m_s-1': ['m/s'],
        'unit:Pa': ['Pa'],
        'unit:percent': ['%']
}

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
    'relativeHumidity': ['Humidity', 'measurement', '%', '%'],
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


def get_obs_station_list(latitude, longitude):
    """Get list of observation stations for a location.

    This gets the list of stations which provide observations
    closest to the given point (latitude, longitude). This is done
    by first getting the information about the point, one item of which
    is the URL for retreiving the list of stations.

    """
    res = requests.get("https://api.weather.gov/points/{},{}".format(
        latitude, longitude), headers=REQUESTS_HEADERS)
    #
    # The API returns a 404 if the location is outside the area NWS handles.
    #
    if res.status_code == 404:
        _LOGGER.error("Location %s,%s is outside of NWS service area",
                      latitude, longitude)
        raise ConfigEntryNotReady

    if res.status_code != 200:
        _LOGGER.error("Error getting metadata for location %s,%s",
                      latitude, longitude)
        raise PlatformNotReady
    try:
        obsurl = res.json()['properties']['observationStations']
    except ValueError:
        raise PlatformNotReady

    res = requests.get(obsurl, headers=REQUESTS_HEADERS)
    if res.status_code == 404:
        _LOGGER.error("Location %s,%s is outside of NWS service area",
                      latitude, longitude)
    if res.status_code != 200:
        _LOGGER.error("Error getting station list for location %s,%s",
                      latitude, longitude)
        raise ConfigEntryNotReady
    try:
        return res.json()['features']
    except ValueError:
        _LOGGER.error("No station list retured for location %s,%s",
                      latitude, longitude)
        raise ConfigEntryNotReady


def get_obs_for_station(stationcode, errorstate):
    """Retrieve the latest observation data for the given station.

    This calls the NWS API for to retrieve the latest observation
    measurements from the given weather station. The return value
    is the dictionary under the JSON 'properties' item.
    """
    url = "https://api.weather.gov/stations/{}/observations/latest".format(
        stationcode)
    res = requests.get(url, headers=REQUESTS_HEADERS)
    if res.status_code != 200:
        if not errorstate:
            _LOGGER.error("Cannot get observations for station %s, status=%s",
                          stationcode, res.status_code)
        return None
    try:
        return res.json()['properties']
    except ValueError:
        return None


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NOAA sensor platform.

    The key item is the location to use,
    which can be configured by specifying longitude and latitude.
    If these are not set in the component configuration, the
    longitude and latitude specified in the overall home assistant
    configuration are used.
    Optionally the station code for the observation station, can
    be specified. This must be one which is in the station list
    for the location provided.  If no station code is configured,
    the closest station is chosen.
    """
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
        raise ConfigEntryNotReady
    #
    # Round location items to 4 decimal digits
    #
    latitude = round(latitude, 4)
    longitude = round(longitude, 4)
    #
    # Get the list of observation stations for the location.
    # This checks that the location is within the NWS coverage area.
    #
    try:
        stationlist = get_obs_station_list(latitude, longitude)
    except requests.RequestException:
        _LOGGER.error("Error getting station list for location %s,%s",
                      latitude, longitude)
        raise PlatformNotReady

    if stationlist is None:
        raise ConfigEntryNotReady

    # If no station was configured, use first station from list as the
    # station for observations.  If a station was configured, verify
    # that it is in the list for this location.
    #
    #
    # Do we have a station from the configuration?
    #

    stationcode = None

    #
    # loop through list of stations to check if code is valid station
    # for this location
    #
    for station in stationlist:
        if confstationcode is None:
            stationcode = station['properties']['stationIdentifier']
            stationname = station['properties']['name']
            break
        else:
            if confstationcode == station['properties']['stationIdentifier']:
                stationcode = confstationcode
                stationname = station['properties']['name']
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
        raise ConfigEntryNotReady

    #
    # Create the data object for observations for this location/station.
    #

    noaadata = NOAACurrentData(hass, stationcode,
                               stationname, name)
    #
    # Perform a data update to get first set of data and available
    # measurements
    #
    noaadata.update()
    if not noaadata.data:
        raise PlatformNotReady

    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(NOAACurrentSensor(hass, noaadata, variable, name))

    add_entities(sensors, True)


class NOAACurrentSensor(Entity):
    """Implementation of a NOAA station current sensor.

    Each instance has as attributes the condition name, the
    NOAACurrentCurrentData object, the platform name and the units
    we should record the measurements in. The units are based on whether
    home-assistant has been configured to use metric units or imperial
    units.  The values returned from the NWS API calls are converted to
    the target units, which are the typical units used for that type
    of measurement.
    """

    def __init__(self, hass, noaadata, condition, name):
        """Initialize the sensor object."""
        self._condition = condition
        self._noaadata = noaadata
        self._name = name
        #
        # Set whether desired units are metric (default) or
        # imperial.
        #
        if hass.config.units == METRIC_SYSTEM:
            self._desiredunit = SENSOR_TYPES[condition][2]
        elif hass.config.units == IMPERIAL_SYSTEM:
            self._desiredunit = SENSOR_TYPES[condition][3]
        else:
            _LOGGER.warning("Unknown unit system %s, defaulting to metric",
                            hass.config.units)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self._condition][0])

    def _unit_convert(self, variable, desiredunit):
        """Check if value needs to be converted to different units.

        This will do the appropriate conversion to get the value
        from unit it is supplied in to the standard metric or imperial
        value used for the measurement.
        """
        #
        # No conversion needed if no value
        #
        if variable['value'] is None:
            return None

        result = variable['value']
        #
        # We check if a unit is supplied, and if so we try to covert
        # the value to the desired unit (set at initialization).
        # If we either don't get a unit, or get a unit we don't
        # know how to convert, we will return a null value.
        # Otherwise the value will be converted as required.
        #
        if 'unitCode' not in variable:
            return None

        if variable['unitCode'] not in UNIT_MAPPING:
            _LOGGER.debug("No translation for unitCode %s",
                          variable['unitCode'])
            return None
        #
        # We have a unit mapping to use
        #
        srcunit = UNIT_MAPPING[variable['unitCode']][0]
        _LOGGER.debug("srcunit=%s, desiredunit=%s", srcunit, desiredunit)
        #
        # If source and desired units are the same, no need to convert
        #
        if srcunit == self._desiredunit:
            return result

        # need to conver units, identify conversion required
        #
        # Do we have temperature in Celsius and need Fahrenheit?
        #
        if srcunit == TEMP_CELSIUS and desiredunit == TEMP_FAHRENHEIT:
            return result * 9 / 5 + 32
        #
        # Do we have Fahrenheit and need Celsius
        #
        if srcunit == TEMP_FAHRENHEIT and desiredunit == TEMP_CELSIUS:
            return (result - 32) * 5 / 9
        #
        # Do we have a length in meters?
        #
        if srcunit == LENGTH_METERS:
            # Is the target miles? (Used for visibility)
            if desiredunit == LENGTH_MILES:
                return result / 1609.344
            # Is the target kilometers? (Used for visibility)
            if desiredunit == LENGTH_KILOMETERS:
                return result / 1000
            # Is the target unit millimeters? (Used for precipitation)
            if desiredunit == 'mm':
                return result * 1000
            # Is the target unit inches? (Used for precipitation)
            if desiredunit == LENGTH_INCHES:
                return result * 39.37007874
            # If we have some other target unit we have an error
            # Return the original value
            return result
        #
        # Do we have pressure in Pascals?
        #
        if srcunit == 'Pa' and desiredunit == 'mbar':
            return result / 100
        #
        # Do we have a speed in meters/second (wind speed and gusts)
        #
        if srcunit == 'm/s' and desiredunit == 'mph':
            return result * 2.236936292
        #
        # If we fall through to here we have a unit name in our mapping
        # table but not in the conversion code above.
        # Just return the original value.
        #
        return result

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug("Getting state for %s", self._condition)
        _LOGGER.debug("noaadata.data set is %s", set(self._noaadata.data))
        #
        # ensure we have some data
        #
        if self._condition in self._noaadata.data:
            variable = self._noaadata.data[self._condition]
            _LOGGER.debug("Condition %s value=%s", self._condition, variable)
            #
            # Now check for type of value for this attribute
            #
            if SENSOR_TYPES[self._condition][1] == 'single':
                # attribute itself is the value for single value items
                _LOGGER.debug("Condition %s is single value='%s'",
                              self._condition, variable)
                return variable
            if SENSOR_TYPES[self._condition][1] == 'measurement':
                # value attribute of variable for measurements
                _LOGGER.debug("Condition %s is measurement='%s',\
                               from string '%s'",
                              self._condition, variable['value'], variable)
                if variable['value'] is None:
                    return None
                #
                # Convert to the target units (if required)
                #
                res = self._unit_convert(variable, self._desiredunit)
                if res is None:
                    return res
                return round(res, 1)

            if SENSOR_TYPES[self._condition][1] == 'array':
                # The only array types we know how to handle is cloudLayers
                if self._condition == 'cloudLayers':
                    #
                    # The array for cloudLayers includes a height and
                    # text for each layer.  At this point we will
                    # only deal with the text for the first layer (if any) and
                    # ignore the other values.
                    if variable:
                        return variable[0]['amount']
                    return None
            if SENSOR_TYPES[self._condition][1] is not None:
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
        attr[ATTR_LAST_UPDATE] = self._noaadata.lastupdate
        attr[ATTR_SITE_ID] = self._noaadata.stationcode
        attr[ATTR_SITE_NAME] = self._noaadata.stationname
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measure for the sensor."""
        #
        # ensure we have some data
        #
        if self._condition in self._noaadata.data:
            variable = self._noaadata.data[self._condition]
            #
            # Now check for type of value for this attribute
            # Only measurements have units
            #
            if SENSOR_TYPES[self._condition][1] == 'measurement':
                # We should have a unitCode supplied from the API response.
                if self._desiredunit is not None:
                    return self._desiredunit

                if 'unitCode' in variable:
                    # run it through our mapping table.  If it
                    # doesn't have a map, return the value we recevied.
                    if variable['unitCode'] in UNIT_MAPPING:
                        return UNIT_MAPPING[variable['unitCode']][0]
                    return variable['unitCode']
        return None

    #
    # Handle data update request
    #
    def update(self):
        """Update the sensor data."""
        self._noaadata.update()


#
# class to obtain the data from the NOAA/NWS API
#
class NOAACurrentData(Entity):
    """Get the latest data from NOAA API.

    This uses the API call
    https://api.weather.gov/stations/<stationcode>/observations/latest
    which always returns all measurement names, even when the station does
    not have an instrument for measuring that item. Also, for some measurements
    the API returns a null value when the instrument provides some default
    reading (for example, wind speed will be returned as null when there is
    no measureable wind.
    Also the min and max temperature value, and the last n hour precipitation
    values are not returned with all calls.  It appears that the values
    are only returned for specific observation intervals through the day,
    depending upon the station.
    """

    def __init__(self, hass, stationcode, stationname, name):
        """Initialize the current data object."""
        _LOGGER.debug("Initialize NOAACurrentData with stationcode=%s, "
                      "stationname='%s',name='%s'",
                      stationcode, stationname, name)

        self.stationcode = stationcode
        self.stationname = stationname
        self._name = name
        self.lastupdate = datetime.datetime.now(datetime.timezone.utc)
        self.data = dict()
        self._errorstate = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest observation data from the station."""
        #
        # Log that we were called
        #
        _LOGGER.debug("update called for station %s", self.stationcode)

        try:
            obslist = get_obs_for_station(self.stationcode, self._errorstate)
        except requests.RequestException:
            if not self._errorstate:
                self._errorstate = True
                _LOGGER.error("Cannot get observations for station %s",
                              self.stationcode)
            return
        #
        # Make sure good status result
        #
        if obslist is None:
            if not self._errorstate:
                self._errorstate = True
                _LOGGER.error("No observations for station %s",
                              self.stationcode)
            return
        #
        # Got data, so no longer in error condition
        #
        self._errorstate = False
        #
        # Get the timestamp of the report, if any
        #
        if 'timestamp' in obslist:
            tsstring = obslist['timestamp']
            self.lastupdate = datetime.datetime.strptime(
                '{}{}'.format(tsstring[0:22], tsstring[23:25]),
                '%Y-%m-%dT%H:%M:%S%z')
        _LOGGER.debug("timestamp=%s, obslist properties='%s'",
                      self.lastupdate, obslist)

        #
        # Now loop through all observation values returned and set the
        # condition value
        #
        _LOGGER.debug("checking for variables using set %s intersection \
                       set %s which is '%s'",
                      SENSOR_TYPES_SET, set(obslist),
                      SENSOR_TYPES_SET.intersection(set(obslist)))

        for variable in SENSOR_TYPES_SET.intersection(
                set(obslist)):
            _LOGGER.debug("setting value variable=%s, value='%s'",
                          variable, obslist[variable])
            self.data[variable] = obslist[variable]
