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
                            # "NOAAWeather"
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
        - windSpeed         # sustained wind speed in km/h or mph
        - windDirection     # direction of sustained winds (degrees angle)
        - windGust          # speed of wind gusts in km/h or mph
        - heatIndex         # heat index temperature in degrees C of F
        - barometricPressure    # pressure in mbar
        - seaLevelPressure      # current sea level pressure in mbar
        - precipitationLastHour # liquid precipitation in last hour (mm or in)
        - precipitationLast3Hours # liquid precipitation in last 3 hours (mm
                                # or in). Note that this is only returned
                                # on three hour intervals.
        - precipitationLast6Hours # liquid precipitation in last 6 hours (mm
                                # or in). Note that this is only returned
                                # on six hour intervals.
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
                                # once per day.
        - maxTemperatureLast24Hours # Maximum temperature in the last 24 hours
                                # in degrees C or F.  This is only reported
                                # once per day.

Some notes on the data returned from NOAA/NWS:
Not all stations have the equipment to measure all of the conditions.

"""
import datetime
from datetime import timedelta

import logging

import aiohttp

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA, ENTITY_ID_FORMAT)
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS, CONF_NAME, LENGTH_METERS, TEMP_CELSIUS,
    TEMP_FAHRENHEIT, LENGTH_KILOMETERS, LENGTH_MILES, LENGTH_INCHES,
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_PRESSURE)
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import (
    Entity, async_generate_entity_id)
from homeassistant.util import Throttle
from homeassistant.exceptions import (
    ConfigEntryNotReady, PlatformNotReady)

REQUIREMENTS = ['pynws==0.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NOAA Weather"

#
# The rates at which new measurement values appear varies by station.
# Typically the measurements from airport weather stations will only update
# once an hour, while other stations may provide updated data much more
# frequently. Some of the updates may not have the full set of measurements,
# but all items the station measures should be in the hourly update.
# To avoid having the NWS update cycle and polling mismatch (poll just
# before the update) by an hour, we will allow more frequent
# requests.
#
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
SCAN_INTERVAL = timedelta(minutes=30)

ATTR_LAST_UPDATE = 'last_update'
ATTR_SENSOR_ID = 'sensor_id'
ATTR_SITE_ID = 'site_id'
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
#                       icon, device class
# where type is one of:
#   single - single value, for example textDescription or presentWeather
#   measurement - single measurement as a dictionary of attributes
#                   'unitCode' and 'value' attributes expected
#   array - array of dictionaries.  At this point only case seen
#           is for cloudLayers, with the items 'base':['value','unitCode']
#           and 'amount'

SENSOR_TYPES = {
    'textDescription': ['Weather', 'single', None, None, None, None],
    'presentWeather': ['Present Weather', 'single', None, None, None, None],
    'temperature': ['Temperature', 'measurement',
                    TEMP_CELSIUS, TEMP_FAHRENHEIT,
                    'mdi:thermometer', DEVICE_CLASS_TEMPERATURE],
    'dewpoint': ['dewpoint', 'measurement',
                 TEMP_CELSIUS, TEMP_FAHRENHEIT,
                 'mdi:thermometer', DEVICE_CLASS_TEMPERATURE],
    'windChill': ['Wind Chill', 'measurement',
                  TEMP_CELSIUS, TEMP_FAHRENHEIT,
                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE],
    'heatIndex': ['Heat Index', 'measurement',
                  TEMP_CELSIUS, TEMP_FAHRENHEIT,
                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE],
    'windSpeed': ['Wind Speed', 'measurement',
                  'km/h', 'mph',
                  'mdi:weather-windy', None],
    'windDirection': ['Wind Bearing', 'measurement',
                      '°', '°',
                      'mdi:flag-triangle', None],
    'windGust': ['Wind Gust', 'measurement',
                 'km/h', 'mph', 'mdi:weather-windy', None],
    'barometricPressure': ['Pressure', 'measurement', 'mbar', 'mbar',
                           None, DEVICE_CLASS_PRESSURE],
    'seaLevelPressure': ['Sea Level Pressure', 'measurement',
                         'mbar', 'mbar',
                         None, DEVICE_CLASS_PRESSURE],
    'maxTemperatureLast24Hours': ['Maximum Temperature last 24 Hours',
                                  'measurement', TEMP_CELSIUS,
                                  TEMP_FAHRENHEIT,
                                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE],
    'minTemperatureLast24Hours': ['Minimum Temperature last 24 Hours',
                                  'measurement', TEMP_CELSIUS,
                                  TEMP_FAHRENHEIT,
                                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE],
    'precipitationLastHour': ['Precipitation in last hour', 'measurement',
                              'mm', LENGTH_INCHES,
                              'mdi:cup-water', None],
    'precipitationLast3Hours': ['Precipitation in last 3 hours',
                                'measurement', 'mm', LENGTH_INCHES,
                                'mdi:cup-water', None],
    'precipitationLast6Hours': ['Precipitation in last 6 hours',
                                'measurement', 'mm', LENGTH_INCHES,
                                'mdi:cup-water', None],
    'relativeHumidity': ['Humidity', 'measurement', '%', '%',
                         'mdi:water-percent', DEVICE_CLASS_HUMIDITY],
    'cloudLayers': ['Cloud Layers', 'array', None, None, None, None],
    'visibility': ['Visibility', 'measurement',
                   LENGTH_KILOMETERS, LENGTH_MILES, None, None]
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


async def get_obs_station_list(nws):
    """Get list of observation stations for a location.

    This gets the list of stations which provide observations
    closest to the given point (latitude, longitude).

    """
    import pynws
    res = None
    try:
        res = await nws.stations()
    except pynws.NwsError as status:
        #
        # This is some type of configuration error
        #
        _LOGGER.error("Error getting station list for %s: %s",
                      nws.latlon, status)
        raise ConfigEntryNotReady
    except aiohttp.ClientResponseError as status:
        #
        # Check if the response error is a 404 (not found) or something
        # else. A 404 indicates the location is outside the NOAA/NWS
        # scope, so it is a configuration error.
        if status.args[0][0:3] == '404':
            _LOGGER("location %s outside of NOAA/NWS scope",
                    nws.latlon)
            raise ConfigEntryNotReady
        #
        # Other errors translate into potential temporary errors
        # from the API server, so indicate that the target is not
        # ready.
        #
        _LOGGER.error("Error getting station list for %s: %s",
                      nws.latlon, status)
        raise PlatformNotReady
    except aiohttp.ClientError as status:
        #
        # Here with some type of error that is not due
        # to an HTTP response.  This most likely is due to some intermittent
        # issue with either the API server or the Internet connection to it,
        # so try again later
        _LOGGER.error("Error accessing API for %s: %s",
                      nws.latlon, status)
        raise PlatformNotReady
    #
    # If we didn't get a station value, there is something wrong
    # with the configuration
    #
    if res is None:
        raise ConfigEntryNotReady
    #
    # Return the list of stations.
    #
    return res


async def get_obs_for_station(nws, errorstate):
    """Retrieve the latest observation data for the given station.

    This calls the NWS API for to retrieve the latest sets of observation
    measurements from the given weather station. The return value
    is the sequence of dictionaries under the JSON 'properties' item.
    """
    import pynws
    try:
        res = await nws.observations()
    except pynws.NwsError as status:
        if not errorstate:
            _LOGGER.error("Error getting observations for station %s - %s",
                          nws.station, status)
        return None
    except aiohttp.ClientError as status:
        if not errorstate:
            _LOGGER.error("Error getting observations for station %s - %s",
                          nws.station, status)
        return None
    return res


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
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
    import pynws
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
    # Set up a client aiohttp session for use by the pynws object
    #
    session = aiohttp.ClientSession()
    #
    # Round location items to 4 decimal digits
    #
    latitude = round(latitude, 4)
    longitude = round(longitude, 4)
    #
    # Set up pynws.nws object
    #
    nws = pynws.Nws(session, latlon=(latitude, longitude))
    nws.limit = 5
    #
    # Get the list of observation stations for the location.
    # This checks that the location is within the NWS coverage area.
    #
    stationlist = await get_obs_station_list(nws)

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
            stationcode = station
            break
        else:
            if confstationcode == station:
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
        raise ConfigEntryNotReady
    #
    # Set station code in nws object for future calls
    #
    nws.station = stationcode
    #
    # Create the data object for observations for this location/station.
    #

    noaadata = NOAACurrentData(hass, stationcode, name, nws)
    #
    # Perform a data update to get first set of data and available
    # measurements
    #
    await noaadata.async_update()
    if not noaadata.data:
        raise PlatformNotReady
    _LOGGER.debug("after first update, noaadata.data=%s", noaadata.data)
    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            DEFAULT_NAME + '.' + noaadata.stationcode + '.' + variable,
            hass=hass)
        sensors.append(
            NOAACurrentSensor(hass, noaadata, variable, name, entity_id))
    #
    # Add all the sensors
    #
    async_add_entities(sensors, True)
    return


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

    def __init__(self, hass, noaadata, condition, name, entity_id):
        """Initialize the sensor object."""
        _LOGGER.debug("Initializing sensor %s, condition %s, sensor_type: %s",
                      name, condition, SENSOR_TYPES[condition])
        self._condition = condition
        self._noaadata = noaadata
        self._name = name
        self.entity_id = entity_id
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
        #
        # Set icon and device class, if any
        #
        self._icon = SENSOR_TYPES[condition][4]
        self._device_class = SENSOR_TYPES[condition][5]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self._condition][0])

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Device class of the sensor."""
        return self._device_class

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
        # Even for metric we need to convert meters/second
        #
        if srcunit == 'm/s' and desiredunit == 'km/h':
            return result * 3.6
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
                _LOGGER.debug("Condition %s is measurement='%s', "
                              "from string '%s'",
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
        if self._condition not in self._noaadata.data:
            return None
        attr = {}
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        attr[ATTR_LAST_UPDATE] = self._noaadata.datatime[self._condition]
        attr[ATTR_SITE_ID] = self._noaadata.stationcode
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
    async def async_update(self):
        """Update the sensor data."""
        await self._noaadata.async_update()


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

    def __init__(self, hass, stationcode, name, nws):
        """Initialize the current data object."""
        _LOGGER.debug("Initialize NOAACurrentData with stationcode=%s, "
                      "name='%s'",
                      stationcode, name)

        self.stationcode = stationcode
        self._name = name
        self.nws = nws
        #
        # Set time of last update to two hours ago.  This
        # should ensure that when we get the first set of observations
        # and process those after this time, we will have at least
        # one complete hourly observation record
        #
        self.lastupdate = datetime.datetime.now(datetime.timezone.utc) -\
            timedelta(hours=2)
        self.data = dict()
        self.datatime = dict()
        self._errorstate = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest observation data from the station."""
        #
        # Log that we were called
        #
        _LOGGER.debug("update called for station %s", self.nws.station)

        obslist = await get_obs_for_station(self.nws, self._errorstate)
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
        # Sort the list so that the oldest observations are first
        #
        obslist = sorted(obslist, key=lambda obs: obs['timestamp'])
        for obs in obslist:
            self._process_obs(obs)
        return

    def _process_obs(self, obsprop):
        #
        # Get the timestamp of the report, if any
        #
        _LOGGER.debug("_process_obs called with obsprop=%s", obsprop)
        if 'timestamp' in obsprop:
            tsstring = obsprop['timestamp']
            _LOGGER.debug("timestamp=%s", tsstring)
            thisupdate = datetime.datetime.strptime(
                '{}{}'.format(tsstring[0:22], tsstring[23:25]),
                '%Y-%m-%dT%H:%M:%S%z')
            _LOGGER.debug("previous update=%s, thisupdate=%s, ",
                          self.lastupdate, thisupdate)
            #
            # Check if this update is from before our last update time
            # If so, ignore it.
            #
            if thisupdate <= self.lastupdate:
                return
        else:
            # if no timestamp on the record assume it is current.
            thisupdate = datetime.datetime.now(datetime.timezone.utc)
        #
        # Remember time this update was from
        #
        self.lastupdate = thisupdate

        #
        # Now loop through all observation values returned and set the
        # condition value.
        # We must check whether a value was actually
        # provided, based on the "qualityControl" attribute.
        # Cases are:
        #   qc:Z - this report does not contain a value for this measurement
        #           therefore we will not change the current value.
        #   qc:S - this report contains a valid value for this measurement.
        #           therefore we will update the current value
        #   qc:V - this is used for windChill and heatIndex, which are
        #           based on other values.  Specific checks are done
        #           to determine whether a null value should be set as the
        #           current value.
        #           It is also sometimes used for the pressure items
        #   qc:C - this is used for valid relativeHumidity, visibility and the
        #           precipitation values. Therefore, these values will
        #           update the current value.
        #   null - this is used for min/max temperature values (and maybe
        #           others) when they do not have a valid value.
        #
        _LOGGER.debug("checking for variables using set %s intersection "
                      "set %s which is '%s'",
                      SENSOR_TYPES_SET, set(obsprop),
                      SENSOR_TYPES_SET.intersection(set(obsprop)))

        for variable in SENSOR_TYPES_SET.intersection(
                set(obsprop)):
            _LOGGER.debug("setting value variable=%s, value='%s'",
                          variable, obsprop[variable])
            #
            # If this is the first time we update has been called
            # we need to ensure every variable we want will exist
            # in the dictionary
            #
            if variable not in self.data:
                if SENSOR_TYPES[variable][1] == 'measurement':
                    self.data[variable] = "unknown"
                if SENSOR_TYPES[variable][1] == 'measurement':
                    self.data[variable] = {
                        'value': None,
                        'unitCode': None,
                        'qualityControl': None,
                        }
                if SENSOR_TYPES[variable][2] == 'array':
                    self.data[variable] = dict()
                self.datatime[variable] = thisupdate

            #
            # Check for existance of useable values for
            # measurements.
            #
            if 'qualityControl' in obsprop[variable]:
                qcval = obsprop[variable]['qualityControl']
                if qcval == 'qc:Z':
                    # No update of value
                    continue
                if qcval in ('qc:S', 'qc:C'):
                    # Valid value, just update data.
                    self.data[variable] = obsprop[variable]
                    self.datatime[variable] = thisupdate
                    continue
                #
                # Special case for windChill.  Value is not valid
                # if we don't have valid temperature and windSpeed
                # values, since it is a calculated value based on
                # temperature and wind speed.
                #
                if variable == 'windChill':
                    if 'temperature' not in obsprop or \
                            'windSpeed' not in obsprop:
                        #
                        # If no temperature or windSpeed values
                        # we can't have windChill
                        #
                        continue
                    if 'value' not in obsprop['temperature'] or \
                            'value' not in obsprop['windSpeed']:
                        #
                        # If no values, we can't have windChill
                        #
                        continue
                    if obsprop['temperature']['value'] is None or \
                            (obsprop['windSpeed']['value'] is None):
                        #
                        # If either value is missing, ignore
                        # this value
                        #
                        continue
                    self.data[variable] = obsprop[variable]
                    self.datatime[variable] = thisupdate
                    continue
                #
                # Special case for heatIndex.  Value is not valid
                # if we don't have valid temperature and dewpoint
                # values, since it is a calculated value based on
                # temperature and dewpoint.
                #
                if variable == 'heatIndex':
                    if 'temperature' not in obsprop or \
                            'dewpoint' not in obsprop:
                        #
                        # If no temperature or dewpoint values
                        # we can't have heatIndex
                        #
                        continue
                    if 'value' not in obsprop['temperature'] or \
                            'value' not in obsprop['dewpoint']:
                        #
                        # If no values, we can't have heatIndex
                        #
                        continue
                    if obsprop['temperature']['value'] is None or \
                            obsprop['dewpoint']['value'] is None:
                        #
                        # If either value is missing, ignore
                        # this value
                        #
                        continue
                    self.data[variable] = obsprop[variable]
                    self.datatime[variable] = thisupdate
                    continue
                #
                # Other items, check for qc:V
                #
                if qcval == "qc:V":
                    if 'value' in obsprop[variable]:
                        if obsprop[variable]['value'] is not None:
                            self.data[variable] = obsprop[variable]
                            self.datatime[variable] = thisupdate
                            continue
                #
                # If we have a qualityControl attribute but with a value
                # we don't know about, ignore the item.
                continue
            #
            # Here for values that do not include a qualityControl attribute.
            #

            self.data[variable] = obsprop[variable]
            self.datatime[variable] = thisupdate
        return
