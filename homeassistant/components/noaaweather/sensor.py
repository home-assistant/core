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
    usehaweathercond = <boolean>
                            # If true, use the Home Assistant values
                            # for weather conditions instead of
                            # the native values from textDescription.
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
from typing import Dict, List, Union, Any

import aiohttp
from astral import Location
import voluptuous as vol

from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    CONF_NAME, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE, LENGTH_INCHES, LENGTH_KILOMETERS, LENGTH_METERS,
    LENGTH_MILES, PRESSURE_MBAR, PRESSURE_PA, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.util import Throttle

REQUIREMENTS = ['pynws==0.6', 'metar==1.7.0']

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
CONF_USERAGENT = 'useragent'
CONF_USEHAWEATHER = 'usehaweathercond'

ATTRIBUTION = "Data from NOAA/NWS"

#
# Unit name constants that are not in homeassistant.const yet.
#
LENGTH_MILLIMETERS = 'mm'
ANGLE_DEGREES = '°'
SPEED_METERS_PER_SECOND = 'm/s'
SPEED_MILES_PER_HOUR = 'mph'
SPEED_KM_PER_HOUR = 'km/h'
RATIO_PERCENT = '%'

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
        'unit:degree_(angle)': [ANGLE_DEGREES],
        'unit:m': [LENGTH_METERS],
        'unit:m_s-1': [SPEED_METERS_PER_SECOND],
        'unit:Pa': [PRESSURE_PA],
        'unit:percent': [RATIO_PERCENT]
}

# Sensor types attributes are: Name, type of value,
#                       preferred metric units, preferred imperial units
#                       icon, device class, METAR name, METAR value unit,
#                       unit string to use for METAR value, # digits for
#                       rouning
# where type is one of:
#   single - single value, for example textDescription or presentWeather
#   measurement - single measurement as a dictionary of attributes
#                   'unitCode' and 'value' attributes expected
#   array - array of dictionaries.  At this point only case seen
#           is for cloudLayers, with the items 'base':['value','unitCode']
#           and 'amount', and with presentWeather.
# define names for value types:

VAL_SINGLE = 's'
VAL_MEASUREMENT = 'm'
VAL_ARRAY = 'a'

# Define names for indices

STI_NAME = 0
STI_VALTYPE = 1
STI_METU = 2
STI_IMPU = 3
STI_ICON = 4
STI_DEVC = 5
STI_MNAME = 6
STI_MUNIT = 7
STI_MUSTR = 8
STI_DIGIT = 9


SENSOR_TYPES = {
    'textDescription': ['Weather', VAL_SINGLE, None, None, None, None, None,
                        None, None],
    'presentWeather': ['Present Weather', VAL_ARRAY, None, None, None, None,
                       None, None],
    'temperature': ['Temperature', VAL_MEASUREMENT,
                    TEMP_CELSIUS, TEMP_FAHRENHEIT,
                    'mdi:thermometer', DEVICE_CLASS_TEMPERATURE, 'temp', 'C',
                    'unit:degC', 1],
    'dewpoint': ['Dew Point', VAL_MEASUREMENT,
                 TEMP_CELSIUS, TEMP_FAHRENHEIT,
                 'mdi:thermometer', DEVICE_CLASS_TEMPERATURE, 'dewpt', 'C',
                 'unit:degC', 1],
    'windChill': ['Wind Chill', VAL_MEASUREMENT,
                  TEMP_CELSIUS, TEMP_FAHRENHEIT,
                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE, None, None,
                  None, 1],
    'heatIndex': ['Heat Index', VAL_MEASUREMENT,
                  TEMP_CELSIUS, TEMP_FAHRENHEIT,
                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE, None, None,
                  None, 1],
    'windSpeed': ['Wind Speed', VAL_MEASUREMENT,
                  SPEED_KM_PER_HOUR, SPEED_MILES_PER_HOUR,
                  'mdi:weather-windy', None, 'wind_speed', 'MPS',
                  'unit:m_s-1', 1],
    'windDirection': ['Wind Bearing', VAL_MEASUREMENT,
                      ANGLE_DEGREES, ANGLE_DEGREES,
                      'mdi:flag-triangle', None, 'wind_dir', None,
                      'unit:degree_(angle)', 0],
    'windGust': ['Wind Gust', VAL_MEASUREMENT,
                 SPEED_KM_PER_HOUR, SPEED_MILES_PER_HOUR, 'mdi:weather-windy',
                 None, 'wind_gust', 'MPS', 'unit:m_s-1', 1],
    'barometricPressure': ['Pressure', VAL_MEASUREMENT, PRESSURE_MBAR,
                           PRESSURE_MBAR, None, DEVICE_CLASS_PRESSURE,
                           'press', 'HPA', 'unit:Pa', 2],
    'seaLevelPressure': ['Sea Level Pressure', VAL_MEASUREMENT,
                         PRESSURE_MBAR, PRESSURE_MBAR,
                         None, DEVICE_CLASS_PRESSURE,
                         'press_sea_level', 'HPA', 'unit:Pa', 2],
    'maxTemperatureLast24Hours': ['Maximum Temperature Last 24 Hours',
                                  VAL_MEASUREMENT, TEMP_CELSIUS,
                                  TEMP_FAHRENHEIT,
                                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE,
                                  'max_temp_24hr', 'C', 'unit:degC', 1],
    'minTemperatureLast24Hours': ['Minimum Temperature Last 24 Hours',
                                  VAL_MEASUREMENT, TEMP_CELSIUS,
                                  TEMP_FAHRENHEIT,
                                  'mdi:thermometer', DEVICE_CLASS_TEMPERATURE,
                                  'min_temp_24hr', 'C', 'unit:degc', 1],
    'precipitationLastHour': ['Precipitation in Last Hour', VAL_MEASUREMENT,
                              LENGTH_MILLIMETERS, LENGTH_INCHES,
                              'mdi:cup-water', None,
                              'precip_1hr', 'M', 'unit:m', 3],
    'precipitationLast3Hours': ['Precipitation in Last 3 Hours',
                                VAL_MEASUREMENT, LENGTH_MILLIMETERS,
                                LENGTH_INCHES, 'mdi:cup-water', None,
                                'precip_3hr', 'M', 'unit:m', 3],
    'precipitationLast6Hours': ['Precipitation in Last 6 Hours',
                                VAL_MEASUREMENT, LENGTH_MILLIMETERS,
                                LENGTH_INCHES, 'mdi:cup-water', None,
                                'precip_6hr', 'M', 'unit:m', 3],
    'relativeHumidity': ['Humidity', VAL_MEASUREMENT, RATIO_PERCENT,
                         RATIO_PERCENT, 'mdi:water-percent',
                         DEVICE_CLASS_HUMIDITY, None, None, None, 0],
    'cloudLayers': ['Cloud Layers', VAL_ARRAY, None, None, None, None, None,
                    None],
    'visibility': ['Visibility', VAL_MEASUREMENT,
                   LENGTH_KILOMETERS, LENGTH_MILES, None, None, 'vis', 'M',
                   'unit:m', 0]
}

SENSOR_TYPES_SET = set(SENSOR_TYPES)

#
# Translation from NOAA/NWS weather descriptions to Home Assistant
# values.  Each row has three values: the HA condition text, an array
# of words, of of which must match, and a second array of words, one of which
# must match if one of the first words match (second array might be empty).
# The table must be ordered such that the more specific values before
# a more general value.
#
CONDITION_XLATE = [
        ['lightning', ['Thunderstorm'], ['Vicinity']],
        ['lightning-rainy', ['Thunderstorm'], [None]],
        ['snowy-rainy', ['Snow', 'Freezing', 'Ice'], ['Rain', 'Drizzle']],
        ['snowy', ['Snow', 'Ice Pellets'], ['Rain', 'Drizzle']],
        ['pouring', ['Heavy Rain'], [None]],
        ['rainy', ['Rain', 'Drizzle', 'Showers'], [None]],
        ['windy-variant', ['Windy'], ['Clouds', 'Cloudy', 'Overcast'], [None]],
        ['windy', ['Windy', 'Breeze'], [None]],
        ['fog', ['Fog', 'Haze'], [None]],
        ['hail', ['Hail', 'Ice Pellets', 'Ice Crystals'], [None]],
        ['partlycloudy', ['Partly Cloudy'], [None]],
        ['cloudy', ['Cloudy', 'Overcast'], [None]],
        ['sunny', ['Fair', 'Clear', 'Few Clouds'], [None]],
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_STATIONCODE): cv.string,
    vol.Optional(CONF_USEHAWEATHER, default=False): cv.boolean,
    vol.Optional(CONF_USERAGENT, default='ha-noaaweather'): cv.string,
})


async def get_obs_station_list(nws) -> List[str]:
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
        return None
    except aiohttp.ClientResponseError as status:
        #
        # Check if the response error is a 404 (not found) or something
        # else. A 404 indicates the location is outside the NOAA/NWS
        # scope, so it is a configuration error.
        if status.args[0][0:3] == '404':
            _LOGGER.error("location %s outside of NOAA/NWS scope",
                          nws.latlon)
            return None
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
    # Return the list of stations.
    #
    return res


async def get_obs_for_station(nws, errorstate) -> Dict:
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


def get_metar_value(metar, variable) -> Dict:
    """Return a variable from the METAR record.

    This returns the VAL_MEASUREMENT dict that corresponds to
    the value provided for the variable in the METAR record that
    was found in the observation.  If there is no value, it will return
    None.
    """
    _LOGGER.debug("Checking for METAR value for %s in %s", variable, metar)

    metaritem = SENSOR_TYPES[variable][STI_MNAME]
    if metaritem is None:
        return None
    metarunit = SENSOR_TYPES[variable][STI_MUNIT]
    if not hasattr(metar, metaritem):
        _LOGGER.debug("No METAR item for %s(%s)", variable, metaritem)
        return None
    #
    # Ensure there is a value
    #
    if not hasattr(getattr(metar, metaritem), 'value'):
        _LOGGER.debug("No metar item %s for %s", metaritem, variable)
        return None

    #
    # We have some value from the METAR record.  Create the
    # dict with 'value', 'unitCode' and 'qualityControl' items
    #
    if metarunit is not None:
        metarvalue = getattr(metar, metaritem).value(units=metarunit)
    else:
        metarvalue = getattr(metar, metaritem).value()
    res = dict()
    res['value'] = metarvalue
    #
    # Deal with units (and one conversion)
    #
    res['unitCode'] = SENSOR_TYPES[variable][STI_MUSTR]
    if metarunit == 'HPA':
        #
        # Special case for pressure, since these normally
        # come back from NOAA/NWS in Pascals, which the Metar
        # object doesn't handle.  So, convert from HPa to Pa
        #
        res['value'] = metarvalue * 100

    res['qualityControl'] = 'qc:S'
    _LOGGER.debug("get_metar_value returning %s", res)
    return res


def textdesctoweather(description) -> str:
    """Convert the values in the textDescription field to HA standard values.

    Home Assistant has some standard text values for current weather
    conditions, which do not have a one to one mapping to the
    weather descriptions used by NOAA/NWS.  This routing will
    convert the text descriptions to the Home Assistant standard text values.
    If no value matches, the original text will be returned.
    """
    _LOGGER.debug("Converting textDescription=%s", description)
    for entry in CONDITION_XLATE:
        for firstword in entry[1]:
            if firstword in description:
                if None in entry[2]:
                    _LOGGER.debug("Found firstword=%s in entry %s",
                                  firstword, str(entry))
                    _LOGGER.debug("Returning %s", entry[0])
                    return entry[0]
                for secondword in entry[2]:
                    if secondword in description:
                        _LOGGER.debug(
                            "Found firstword=%s, secondword=%s in entry %s",
                            firstword, secondword,
                            str(entry))
                        _LOGGER.debug("Returning %s", entry[0])
                        return entry[0]
                _LOGGER.debug("Found firstword=%s in entry %s",
                              firstword, str(entry))
                _LOGGER.debug("Returning %s", entry[0])
                return entry[0]
    _LOGGER.debug("No matching condition found for %s", description)
    return description


def unit_convert(variable, desiredunit) -> float:
    """Convert the measurement from the native unit to the appropriate unit.

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
    #
    # If source and desired units are the same, no need to convert
    #
    if srcunit == desiredunit:
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
        if desiredunit == LENGTH_MILLIMETERS:
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
    if srcunit == PRESSURE_PA and desiredunit == PRESSURE_MBAR:
        return result / 100
    #
    # Do we have a speed in meters/second (wind speed and gusts)
    #
    if srcunit == SPEED_METERS_PER_SECOND and \
            desiredunit == SPEED_MILES_PER_HOUR:
        return result * 2.236936292
    #
    # Even for metric we need to convert meters/second
    #
    if srcunit == SPEED_METERS_PER_SECOND and \
            desiredunit == SPEED_KM_PER_HOUR:
        return result * 3.6
    #
    # If we fall through to here we have a unit name in our mapping
    # table but not in the conversion code above.
    # Just return the original value.
    #
    return result


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None) -> None:
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
    session = async_get_clientsession(hass)
    #
    # Round location items to 4 decimal digits, since that is what the
    # API wants.
    #
    latitude = round(latitude, 4)
    longitude = round(longitude, 4)
    #
    # Set up pynws.nws object
    #
    nws = pynws.Nws(session, latlon=(latitude, longitude))
    nws.userid = config.get(CONF_USERAGENT)
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

    stationcode = None

    #
    # loop through list of stations to check if configured station
    # is valid for this location, or use first station
    # if none is configured.  The first station will be the closest
    # one to the point given.
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

    noaadata = NOAACurrentData(stationcode, name, nws,
                               latitude, longitude)
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
            NOAACurrentSensor(noaadata, variable, name, entity_id,
                              config.get(CONF_USEHAWEATHER),
                              hass.config.units.is_metric))
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

    def __init__(self, noaadata, condition, name, entity_id,
                 usehaweather, metricunits) -> None:
        """Initialize the sensor object."""
        _LOGGER.debug("Initializing sensor %s, condition %s, sensor_type: %s",
                      name, condition, SENSOR_TYPES[condition])
        self._condition = condition
        self._noaadata = noaadata
        self._name = name
        self.entity_id = entity_id
        self._usehaweather = usehaweather
        #
        # Set whether desired units are metric (default) or
        # imperial.
        #
        if metricunits:
            self._desiredunit = SENSOR_TYPES[condition][STI_METU]
        else:
            self._desiredunit = SENSOR_TYPES[condition][STI_IMPU]
        #
        # Set icon and device class, if any
        #
        self._icon = SENSOR_TYPES[condition][STI_ICON]
        self._device_class = SENSOR_TYPES[condition][STI_DEVC]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return '{} {}'.format(
            self._name, SENSOR_TYPES[self._condition][STI_NAME])

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Device class of the sensor."""
        return self._device_class

    @property
    def state(self) -> Union[str, float]:
        """Return the state of the sensor."""
        _LOGGER.debug("Getting state for %s", self._condition)
        _LOGGER.debug("noaadata.data set is %s", set(self._noaadata.data))

        if self._condition in self._noaadata.data:
            condvalue = self._noaadata.data[self._condition]
            _LOGGER.debug("Condition %s value=%s", self._condition, condvalue)
            #
            # Now check for type of value for this attribute
            #
            if SENSOR_TYPES[self._condition][STI_VALTYPE] == VAL_SINGLE:
                # attribute itself is the value for single value items
                _LOGGER.debug("Condition %s is single value='%s'",
                              self._condition, condvalue)
                if self._condition == "textDescription" and self._usehaweather:
                    res = textdesctoweather(condvalue)
                    if res == 'sunny' and self._noaadata.isnight:
                        res = 'clear-night'
                    return res
                return condvalue
            if SENSOR_TYPES[self._condition][STI_VALTYPE] == VAL_MEASUREMENT:
                # value attribute of condvalue for measurements
                _LOGGER.debug("Condition %s is measurement='%s', "
                              "from string '%s'",
                              self._condition, condvalue['value'], condvalue)
                if condvalue['value'] is None:
                    return None
                #
                # Convert to the target units (if required)
                #
                res = unit_convert(condvalue, self._desiredunit)
                if res is None:
                    return res
                return round(res, SENSOR_TYPES[self._condition][STI_DIGIT])

            if SENSOR_TYPES[self._condition][STI_VALTYPE] == VAL_ARRAY:
                # The only array types we know how to handle is cloudLayers
                if self._condition == 'cloudLayers':
                    #
                    # The array for cloudLayers includes a height and
                    # text for each layer.  At this point we will
                    # only deal with the text for the first layer (if any) and
                    # ignore the other values.
                    if condvalue:
                        return condvalue[0]['amount']
                    return None

            if SENSOR_TYPES[self._condition][STI_VALTYPE] is not None:
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
    def device_state_attributes(self) -> Any:
        """Return the state attributes of the device."""
        if self._condition not in self._noaadata.data:
            return None
        attr = {}
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        attr[ATTR_LAST_UPDATE] = self._noaadata.datatime[self._condition]
        attr[ATTR_SITE_ID] = self._noaadata.stationcode
        return attr

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measure for the sensor."""
        #
        # ensure we have some data
        #
        if self._condition in self._noaadata.data:
            #
            # Now check for type of value for this attribute
            # Only measurements have units
            #
            if SENSOR_TYPES[self._condition][STI_VALTYPE] == VAL_MEASUREMENT:
                # We should have a unitCode supplied from the API response.
                if self._desiredunit is not None:
                    return self._desiredunit

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

    def __init__(
            self, stationcode, name, nws, latitude, longitude) -> None:
        """Initialize the current data object."""
        _LOGGER.debug("Initialize NOAACurrentData with stationcode=%s, "
                      "name='%s'",
                      stationcode, name)

        self.stationcode = stationcode
        self._name = name
        self.nws = nws
        #
        # Set up astral location object for this location.
        # Note that since astral calculates the times for a current
        # date, we need to have an idea of what offset from GMT the location
        # has.  To get this, we will get the solar noon for both the
        # actual location and for the location at 0,0.  The difference
        # of these gives a good idea of the offset (note, this is not the
        # timezone, but the solar time difference.
        #
        self.astlocation = Location()
        self.astlocation.name = stationcode
        self.astlocation.region = 'US'
        self.astlocation.timezone = 'UTC'
        self.astlocation.latitude = 0
        self.astlocation.longitude = 0
        zerozeronoon = self.astlocation.solar_noon(local=False)
        self.astlocation.latitude = latitude
        self.astlocation.longitude = longitude
        self._timeoffset = zerozeronoon - \
            self.astlocation.solar_noon(local=False)
        #
        # Set time of last update to two hours ago.  This
        # should ensure that when we get the first set of observations
        # and process those after this time, we will have at least
        # one complete hourly observation record
        #
        self.lastupdate = datetime.datetime.now(datetime.timezone.utc) -\
            timedelta(hours=2)
        self.nightstart, self.nightend = self.astlocation.night(
            date=self.lastupdate + self._timeoffset)
        self.isnight = self.lastupdate >= self.nightstart and \
            self.lastupdate <= self.nightend
        self.data = dict()
        self.datatime = dict()
        self._errorstate = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
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
        obslist = sorted(obslist, key=self._obssortkey)
        for obs in obslist:
            self._process_obs(obs)
        return

    @staticmethod
    def _obssortkey(obs) -> Union[str, int]:
        """Return key to sort observation list with.

        Normally this is timestamp, but if timestamp is not in the
        entries we will just use the same value for all
        entries
        """
        if 'timestamp' in obs:
            return obs['timestamp']
        return '0000-00-00T00:00:00+00:00'

    def _process_obs(self, obsprop) -> None:
        from metar import Metar
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
        # Check if moving beyond last night end time
        #
        if self.lastupdate > self.nightend:
            self.nightstart, self.nightend = self.astlocation.night(
                date=self.lastupdate + self._timeoffset,
                local=False, use_elevation=False)
        self.isnight = self.lastupdate >= self.nightstart and \
            self.lastupdate <= self.nightend
        #
        # Check if observation has a "rawMessage" attribute.  This contains
        # the METAR format record, and may have valid information
        # for some of the measurements that are not returned in the
        # individual measurement item.
        #
        if 'rawMessage' in obsprop:
            if obsprop['rawMessage'] is None:
                metar = None
            else:
                #
                # parse the METAR message so that we can use the values
                # if not in individual measurement item.
                #
                try:
                    metar = Metar.Metar(obsprop['rawMessage'])
                except Metar.ParserError:
                    metar = None

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

        for condition in SENSOR_TYPES_SET.intersection(
                set(obsprop)):
            _LOGGER.debug("setting value condition=%s, value='%s'",
                          condition, obsprop[condition])
            #
            # If this is the first time we update has been called
            # we need to ensure every condition we want will exist
            # in the dictionary
            #
            if condition not in self.data:
                if SENSOR_TYPES[condition][STI_VALTYPE] == VAL_SINGLE:
                    self.data[condition] = "unknown"
                if SENSOR_TYPES[condition][STI_VALTYPE] == VAL_MEASUREMENT:
                    self.data[condition] = {
                        'value': None,
                        'unitCode': None,
                        'qualityControl': None,
                        }
                if SENSOR_TYPES[condition][STI_VALTYPE] == VAL_ARRAY:
                    self.data[condition] = dict()
                self.datatime[condition] = thisupdate

            #
            # Check for existance of useable values for
            # measurements.
            #
            if 'qualityControl' in obsprop[condition]:
                qcval = obsprop[condition]['qualityControl']
                if qcval == 'qc:Z':
                    # No update of value in individual entry
                    # check if we have a metar value
                    if metar is None:
                        continue
                    res = get_metar_value(metar, condition)
                    if res is not None:
                        _LOGGER.debug(
                            "using Metar value %s for %s instead of %s",
                            res, condition, obsprop[condition])
                        self.data[condition] = res
                        self.datatime[condition] = thisupdate
                    if condition != 'windGust':
                        continue
                    #
                    # Special case for windGust - if it has
                    # qc:Z it may be because there are no
                    # current gusts, not because the value
                    # is missing. Check if there is a valid
                    # value for windSpeed.
                    #
                    if 'windSpeed' not in obsprop:
                        continue
                    if 'qualityControl' not in obsprop[condition]:
                        continue
                    if obsprop['windSpeed']['qualityControl'] == 'qc:Z' and \
                            get_metar_value(metar, 'windSpeed') is None:
                        self.data[condition] = obsprop[condition]
                        self.datatime[condition] = thisupdate
                        continue
                    continue
                if qcval in ('qc:S', 'qc:C'):
                    # Valid value, just update data.
                    self.data[condition] = obsprop[condition]
                    self.datatime[condition] = thisupdate
                    continue
                #
                # Special case for windChill.  Value is not valid
                # if we don't have valid temperature and windSpeed
                # values, since it is a calculated value based on
                # temperature and wind speed.
                #
                if condition == 'windChill':
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
                    self.data[condition] = obsprop[condition]
                    self.datatime[condition] = thisupdate
                    continue
                #
                # Special case for heatIndex.  Value is not valid
                # if we don't have valid temperature and dewpoint
                # values, since it is a calculated value based on
                # temperature and dewpoint.
                #
                if condition == 'heatIndex':
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
                    self.data[condition] = obsprop[condition]
                    self.datatime[condition] = thisupdate
                    continue
                #
                # Other items, check for qc:V
                #
                if qcval == 'qc:V':
                    if 'value' in obsprop[condition]:
                        if obsprop[condition]['value'] is not None:
                            self.data[condition] = obsprop[condition]
                            self.datatime[condition] = thisupdate
                            continue
                #
                # If we have a qualityControl attribute but with a value
                # we don't know about, ignore the item.
                continue
            #
            # Here for values that do not include a qualityControl attribute.
            #

            self.data[condition] = obsprop[condition]
            self.datatime[condition] = thisupdate
        return
