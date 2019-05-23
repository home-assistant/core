#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Simple service for SL (Storstockholms Lokaltrafik)."""

import datetime
import json
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_FRIENDLY_NAME, CONF_SCAN_INTERVAL,
                                 CONF_SENSOR_TYPE, CONF_SENSORS, STATE_OFF,
                                 STATE_ON)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (async_track_point_in_utc_time,
                                         async_track_utc_time_change,
                                         track_time_interval)
from homeassistant.util import Throttle
from homeassistant.util.dt import now

__version__ = '2.1.0'
_LOGGER = logging.getLogger(__name__)
DOMAIN = 'hasl'

# Keys used in the configuration.
CONF_RI4_KEY = 'ri4key'
CONF_SI2_KEY = 'si2key'
CONF_TL2_KEY = 'tl2key'
CONF_SITEID = 'siteid'
CONF_LINES = 'lines'
CONF_DIRECTION = 'direction'
CONF_ENABLED_SENSOR = 'sensor'
CONF_TIMEWINDOW = 'timewindow'
CONF_SENSORPROPERTY = 'property'
CONF_TRAIN_TYPE = 'train_type'
CONF_TRAFFIC_CLASS = 'traffic_class'
CONF_VERSION = 'version_sensor'
CONF_USE_MINIMIZATION = 'api_minimization'

# Default values for configuration.
DEFAULT_INTERVAL = timedelta(minutes=10)
DEFAULT_TIMEWINDOW = 30
DEFAULT_DIRECTION = '0'
DEFAULT_SENSORPROPERTY = 'min'
DEFAULT_TRAFFIC_CLASS = 'metro,train,local,tram,bus,fer'
DEFAULT_TRAIN_TYPE = 'PT'

DEFAULT_SENSORTYPE = 'dep'
DEFAULT_CACHE_FILE = 'haslcache.json'

# Defining the configuration schema.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    # API Keys
    vol.Optional(CONF_RI4_KEY): cv.string,
    vol.Optional(CONF_SI2_KEY): cv.string,
    vol.Optional(CONF_TL2_KEY): cv.string,
    vol.Optional(CONF_VERSION, default=False): cv.boolean,
    vol.Optional(CONF_USE_MINIMIZATION, default=True): cv.boolean,

    vol.Required(CONF_SENSORS, default=[]):
        vol.All(cv.ensure_list, [vol.All({

            vol.Required(ATTR_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_SENSOR_TYPE, default=DEFAULT_SENSORTYPE):
                vol.In(['departures', 'status', 'trainlocation',
                        'comb', 'tl2']),

            vol.Optional(CONF_ENABLED_SENSOR): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL):
                vol.Any(cv.time_period, cv.positive_timedelta),

            vol.Optional(CONF_SITEID): cv.string,
            vol.Optional(CONF_LINES): cv.string,
            vol.Optional(CONF_DIRECTION, default=DEFAULT_DIRECTION): cv.string,
            vol.Optional(CONF_TIMEWINDOW, default=DEFAULT_TIMEWINDOW):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
            vol.Optional(CONF_SENSORPROPERTY, default=DEFAULT_SENSORPROPERTY):
                vol.In(['min', 'time', 'deviations', 'refresh', 'updated']),

            vol.Optional(CONF_TRAFFIC_CLASS, default=DEFAULT_TRAFFIC_CLASS):
                cv.string,

            vol.Optional(CONF_TRAIN_TYPE, default=DEFAULT_TRAIN_TYPE):
                vol.In(['PT', 'RB', 'TVB', 'SB', 'LB',
                        'SpvC', 'TB1', 'TB2', 'TB3']),
            })]),
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensors."""

    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = {}

    sensors = []

    if config[CONF_VERSION]:
        sensors.append(SLVersionSensor(hass))

    for sensorconf in config[CONF_SENSORS]:

        if sensorconf[CONF_SENSOR_TYPE] == 'departures' or \
           sensorconf[CONF_SENSOR_TYPE] == 'comb':

            sitekey = sensorconf.get(CONF_SITEID)
            si2key = config.get(CONF_SI2_KEY)
            ri4key = config.get(CONF_RI4_KEY)
            if sitekey and ri4key:
                sensorname = sensorconf[ATTR_FRIENDLY_NAME]
                sensors.append(SLDeparturesSensor(
                    hass,
                    si2key,
                    ri4key,
                    sitekey,
                    sensorconf.get(CONF_LINES),
                    sensorname,
                    sensorconf.get(CONF_ENABLED_SENSOR),
                    sensorconf.get(CONF_SCAN_INTERVAL),
                    sensorconf.get(CONF_DIRECTION),
                    sensorconf.get(CONF_TIMEWINDOW),
                    sensorconf.get(CONF_SENSORPROPERTY),
                    config.get(CONF_USE_MINIMIZATION)
                    ))

                _LOGGER.info("Created departures sensor %s...", sensorname)
            else:
                _LOGGER.error("Sensor %s is missing site, si2key or ri4key",
                              sensorconf[ATTR_FRIENDLY_NAME])

        if sensorconf[CONF_SENSOR_TYPE] == 'status' or \
           sensorconf[CONF_SENSOR_TYPE] == 'tl2':

            tl2key = config.get(CONF_TL2_KEY)
            if tl2key:
                sensorname = sensorconf[ATTR_FRIENDLY_NAME]
                sensors.append(SLStatusSensor(
                    hass,
                    tl2key,
                    sensorname,
                    sensorconf.get(CONF_ENABLED_SENSOR),
                    sensorconf.get(CONF_SCAN_INTERVAL),
                    sensorconf.get(CONF_TRAFFIC_CLASS),
                    config.get(CONF_USE_MINIMIZATION)
                    ))

                _LOGGER.info("Created status sensor %s...", sensorname)
            else:
                _LOGGER.error("Sensor %s is missing tl2key attribute",
                              sensorconf[ATTR_FRIENDLY_NAME])

        if sensorconf[CONF_SENSOR_TYPE] == 'trainlocation':
            train_type = sensorconf.get(CONF_TRAIN_TYPE)
            if train_type:
                sensorname = sensorconf[ATTR_FRIENDLY_NAME]
                sensors.append(SLTrainLocationSensor(
                    hass,
                    sensorname,
                    train_type,
                    sensorconf.get(CONF_SCAN_INTERVAL),
                    sensorconf.get(CONF_ENABLED_SENSOR),
                    ))

                _LOGGER.info("Created train sensor %s...", sensorname)
            else:
                _LOGGER.error("Sensor %s is missing train_type attribute",
                              sensorconf[ATTR_FRIENDLY_NAME])

    add_devices(sensors)


class SLVersionSensor(Entity):
    """Trafic Situation Sensor."""
    def __init__(self, hass):

        from hasl import haslapi
        self._hass = hass
        self._haslapi = haslapi()
        self._name = 'HASL Version'
        self._version = __version__
        self._py_version = self._haslapi.version()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """ Return the icon for the frontend."""
        return None

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes."""
        return {'hasl': self._version, 'pyHasl': self._py_version}

    @property
    def state(self):
        """ Return the state of the sensor."""
        return self._version + "/" + self._py_version


class SLTrainLocationSensor(Entity):
    """Trafic Situation Sensor."""
    def __init__(self, hass, friendly_name, train_type,
                 interval, enabled_sensor):

        from hasl import fpapi
        self._hass = hass
        self._fpapi = fpapi()
        self._name = friendly_name
        self._interval = interval
        self._enabled_sensor = enabled_sensor
        self._train_type = train_type
        self._data = {}

        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """ Return the icon for the frontend."""
        return None

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes."""
        return {'type': self._train_type, 'data': json.dumps(self._data)}

    @property
    def state(self):
        """ Return the state of the sensor."""
        return self._train_type

    def _update(self):

        if self._enabled_sensor is not None:
            sensor_state = self._hass.states.get(self._enabled_sensor)

        if self._enabled_sensor is None or sensor_state.state is STATE_ON:

            try:
                apidata = self._fpapi.request(self._train_type)

            except HASL_Error as e:
                _LOGGER.error("A communication error occured while"
                              "updating train location sensor: %s", e.details)
                return

            except Exception as e:
                _LOGGER.error("A error occured while"
                              "updating train location sensor: %s", e)
                return

        self._data = apidata

        _LOGGER.info("Update completed %s...", self._name)


class SLStatusSensor(Entity):
    """Trafic Situation Sensor."""
    def __init__(self, hass, tl2key, friendly_name,
                 enabled_sensor, interval, type,
                 minimization):

        from hasl import tl2api
        self._tl2api = tl2api(tl2key)
        self._datakey = 'tl2_' + tl2key
        self._interval = interval
        self._hass = hass
        self._name = friendly_name
        self._enabled_sensor = enabled_sensor
        self._type = type
        self._sensordata = []
        self._lastupdate = '-'
        self._cachefile = hass.config.path(DEFAULT_CACHE_FILE)
        self._minimization = minimization

        if not hass.data[DOMAIN].get(self._datakey):
            hass.data[DOMAIN][self._datakey] = ''

        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """ Return the icon for the frontend."""
        return 'mdi:train-car'

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes."""
        return self._sensordata

    @property
    def state(self):
        """ Return the state of the sensor."""
        return self._lastupdate

    def getCache(self, key):
        try:
            jsonFile = open(self._cachefile, 'r')
            data = json.load(jsonFile)
            jsonFile.close()

            return data.get(key)
        except:
            return {}

    def putCache(self, key, value):
        try:
            jsonFile = open(self._cachefile, 'r')
            data = json.load(jsonFile)
            jsonFile.close()

            data[key] = value
        except:
            data = {'' + key + '': value}

        jsonFile = open(self._cachefile, 'w')
        jsonFile.write(json.dumps(data))
        jsonFile.close()

    def _update(self):

        if self._enabled_sensor is not None:
            sensor_state = self._hass.states.get(self._enabled_sensor)

        if self._enabled_sensor is None or sensor_state.state is STATE_ON:

            _LOGGER.info("Starting to update TL2 for %s...",
                         self._name)

            # Object used to create our object.
            newdata = {}

            # Use some nice translations for the statuses etc.
            statuses = {
                'EventGood': 'Good',
                'EventMinor': 'Minor',
                'EventMajor': 'Closed',
                'EventPlanned': 'Planned',
                }

            # Icon table used for HomeAssistant.
            statusIcons = {
                'EventGood': 'mdi:check',
                'EventMinor': 'mdi:clock-alert-outline',
                'EventMajor': 'mdi:close',
                'EventPlanned': 'mdi:triangle-outline'
                }

            trafficTypeIcons = {
                'ferry': 'mdi:ferry',
                'bus': 'mdi:bus',
                'tram': 'mdi:tram',
                'train': 'mdi:train',
                'local': 'mdi:train-variant',
                'metro': 'mdi:subway-variant'
                }

            # If the same API have already made the request in within
            # the specified interval then use that data instead of
            # requesting it again and spare some innocent credits from dying.
            cacheage = self._hass.data[DOMAIN][self._datakey]
            if not cacheage or now(self._hass.config.time_zone) \
                    - self._interval > cacheage or not self._minimization:

                try:
                    apidata = self._tl2api.request()
                    apidata = apidata['ResponseData']['TrafficTypes']

                    self.putCache(self._datakey, apidata)
                    self._hass.data[DOMAIN][self._datakey] = \
                        now(self._hass.config.time_zone)

                    _LOGGER.info("Updated cache for %s...", self._name)

                except HASL_Error as e:
                    _LOGGER.error("A communication error occured while"
                                  "updating TL2 sensor: %s", e.details)
                    return

                except Exception as e:
                    _LOGGER.error("A error occured while"
                                  "updating TL4 API: %s", e)
                    return

            else:
                apidata = self.getCache(self._datakey)
                _LOGGER.info("Reusing data from cache for %s...",
                             self._name)

            # Return only the relevant portion of the results.
            for response in apidata:
                type = response['Type']
                if self._type is None or type in self._type:
                    statustype = ('ferry' if type == 'fer' else type)
                    newdata[statustype + '_status'] = \
                        statuses.get(response['StatusIcon'])
                    newdata[statustype + '_status_icon'] = \
                        statusIcons.get(response['StatusIcon'])
                    newdata[statustype + '_icon'] = \
                        trafficTypeIcons.get(statustype)

                    for event in response['Events']:
                        event['Status'] = statuses.get(event['StatusIcon'])
                        event['StatusIcon'] = \
                            statusIcons.get(event['StatusIcon'])

                    newdata[statustype + '_events'] = response['Events']

            # Attribution and update sensor data.
            newdata['attribution'] = "Stockholms Lokaltrafik"
            newdata['last_updated'] = \
                self._hass.data[DOMAIN][self._datakey].strftime('%Y-%m-%d' +
                                                                '%H:%M:%S')
            self._sensordata = newdata
            self._lastupdate = newdata['last_updated']

            _LOGGER.info("TL2 update completed for %s...", self._name)


class SLDeparturesSensor(Entity):
    """Departure board for one SL site."""

    def __init__(self, hass, si2key, ri4key, siteid,
                 lines, friendly_name, enabled_sensor,
                 interval, direction, timewindow, sensorproperty,
                 minimization):
        """Initialize"""

        # The table of resulttypes and the corresponding units of measure.
        unit_table = {
            'min': 'min',
            'time': '',
            'deviations': '',
            'refresh': '',
            'update': '',
            }

        # Setup API and stuff needed for internal processing.
        from hasl import ri4api, si2api
        self._si2key = si2key
        self._ri4key = ri4key
        self._ri4api = ri4api(ri4key, siteid, 60)
        self._si2api = si2api(si2key, siteid, '')
        self._ri4datakey = 'ri2_' + ri4key + '_' + siteid
        self._si2datakey = 'si2_' + si2key + '_' + siteid
        self._hass = hass
        self._name = friendly_name
        self._lines = lines
        self._siteid = siteid
        self._enabled_sensor = enabled_sensor
        self._sensorproperty = sensorproperty
        self._departure_table = []
        self._deviations_table = []
        self._direction = direction
        self._timewindow = timewindow
        self._nextdeparture_minutes = '0'
        self._nextdeparture_expected = '-'
        self._lastupdate = '-'
        self._interval = interval
        self._unit_of_measure = unit_table.get(self._sensorproperty, 'min')
        self._cachefile = hass.config.path(DEFAULT_CACHE_FILE)
        self._minimization = minimization

        if not hass.data[DOMAIN].get(self._ri4datakey):
            hass.data[DOMAIN][self._ri4datakey] = ''

        if self._si2key:
            if not hass.data[DOMAIN].get(self._si2datakey):
                hass.data[DOMAIN][self._si2datakey] = ''

        # Setup updating of the sensor.
        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """ Return the icon for the frontend."""

        if self._deviations_table:
            return 'mdi:bus-alert'

        return 'mdi:bus'

    @property
    def state(self):
        """ Return number of minutes to the next departure """

        # If the sensor should return minutes to next departure.
        if self._sensorproperty is 'min':
            if not self._departure_table:
                return '-'
            return self._departure_table[0]['time']

        # If the sensor should return the time at which next departure occurs.
        if self._sensorproperty is 'time':
            if not self._departure_table:
                return '-'
            expected = self._departure_table[0]['expected'] or '-'
            if expected is not '-':
                expected = \
                    datetime.datetime.strptime(self._nextdeparture_expected,
                                               '%Y-%m-%dT%H:%M:%S')
                expected = expected.strftime('%H:%M:%S')
            return expected

        # If the sensor should return the number of deviations.
        if self._sensorproperty is 'deviations':
            return len(self._deviations_table)

        # If the sensor should return if it is updating or not.
        if self._sensorproperty is 'refresh':
            if self._enabled_sensor is None or sensor_state.state is STATE_ON:
                return STATE_ON
            return STATE_OFF

        if self._sensorproperty is 'updated':
            if self._lastupdate is '-':
                return '-'
            return refresh.strftime('%Y-%m-%d %H:%M:%S')

        # Failsafe
        return '-'

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes ."""

        # Initialize the state attributes.
        val = {}

        # Format the next exptected time.
        if self._departure_table:
            expected_time = self._departure_table[0]['expected'] or '-'
            expected_minutes = self._departure_table[0]['time'] or '-'
            if expected_time is not '-':
                expected_time = \
                    datetime.datetime.strptime(expected_time,
                                               '%Y-%m-%dT%H:%M:%S')
                expected_time = expected_time.strftime('%H:%M:%S')
        else:
            expected_time = '-'
            expected_minutes = '-'

        # Format the last refresh time.
        refresh = self._lastupdate
        if self._lastupdate is not '-':
            refresh = refresh.strftime('%Y-%m-%d %H:%M:%S')

        # Setup the unit of measure.
        if self._unit_of_measure is not '':
            val['unit_of_measurement'] = self._unit_of_measure

        # Check if sensor is currently updating or not.
        if self._enabled_sensor is not None:
            sensor_state = self._hass.states.get(self._enabled_sensor)

        if self._enabled_sensor is None or sensor_state.state is STATE_ON:
            val['refresh_enabled'] = STATE_ON
        else:
            val['refresh_enabled'] = STATE_OFF

        # Set values of the sensor.
        val['attribution'] = 'Stockholms Lokaltrafik'
        val['departures'] = self._departure_table
        val['deviations'] = self._deviations_table
        val['last_refresh'] = refresh
        val['next_departure_minutes'] = expected_minutes
        val['next_departure_time'] = expected_time
        val['deviation_count'] = len(self._deviations_table)

        return val

    def parseDepartureTime(self, t):
        """ weird time formats from the API,
        do some quick and dirty conversions. """

        try:
            if t == 'Nu':
                return 0
            s = t.split()
            if len(s) > 1 and s[1] == 'min':
                return int(s[0])
            s = t.split(':')
            if len(s) > 1:
                rightnow = now(self._hass.config.time_zone)
                min = int(s[0]) * 60 + int(s[1]) - (rightnow.hour * 60 +
                                                    rightnow.minute)
                if min < 0:
                    min = min + 1440
                return min
        except Exception:
            _LOGGER.warning("Failed to parse departure time (%s) ", t)
        return 0

    def getCache(self, key):
        try:
            jsonFile = open(self._cachefile, 'r')
            data = json.load(jsonFile)
            jsonFile.close()

            return data.get(key)
        except:
            return {}

    def putCache(self, key, value):
        try:
            jsonFile = open(self._cachefile, 'r')
            data = json.load(jsonFile)
            jsonFile.close()

            data[key] = value
        except:
            data = {'' + key + '': value}

        jsonFile = open(self._cachefile, 'w')
        jsonFile.write(json.dumps(data))
        jsonFile.close()

    def _update(self):
        """Get the departure board."""

        # If using external sensor, get its value.
        if self._enabled_sensor is not None:
            sensor_state = self._hass.states.get(self._enabled_sensor)

        # If we dont have external sensor or it is ON then proceed.
        if self._enabled_sensor is None or sensor_state.state \
                is STATE_ON:

            self._update_ri4()

            if self._si2key:
                self._update_si2()

            self._lastupdate = now(self._hass.config.time_zone)

    def _update_ri4(self):
        errorOccured = False
        _LOGGER.info("Starting to update RI4 for %s...", self._name)

        cacheage = self._hass.data[DOMAIN][self._ri4datakey]
        if not cacheage or now(self._hass.config.time_zone) \
                - self._interval > cacheage or not self._minimization:

            try:
                departuredata = self._ri4api.request()
                departuredata = departuredata['ResponseData']

                self.putCache(self._ri4datakey, departuredata)
                self._hass.data[DOMAIN][self._ri4datakey] = \
                    now(self._hass.config.time_zone)

                _LOGGER.info("Updated cache for %s...", self._name)

            except HASL_Error as e:
                _LOGGER.error("A communication error occured while"
                              "updating SI2 sensor: %s", e.details)
                errorOccured = True

            except Exception as e:
                _LOGGER.error("A communication error occured while"
                              "updating RI4 API: %s", e)
                errorOccured = True

        else:
            try:
                departuredata = self.getCache(self._ri4datakey)

                _LOGGER.info("Reusing data from cache for %s...",
                             self._name)
            except Exception as e:
                _LOGGER.error("A error occured while retreiving"
                              "cached RI4 sensor data: %s", e)
                errorOccured = True

        if not errorOccured:
            departures = []

            iconswitcher = {
                'Buses': 'mdi:bus',
                'Trams': 'mdi:tram',
                'Ships': 'mdi:ferry',
                'Metros': 'mdi:subway-variant',
                'Trains': 'mdi:train',
                }

            for (i, traffictype) in enumerate(['Metros', 'Buses', 'Trains',
                                               'Trams', 'Ships']):

                for (idx, value) in enumerate(departuredata[traffictype]):
                    direction = value['JourneyDirection'] or 0
                    displaytime = value['DisplayTime'] or ''
                    destination = value['Destination'] or ''
                    linenumber = value['LineNumber'] or ''
                    expected = value['ExpectedDateTime'] or ''
                    icon = iconswitcher.get(traffictype, 'mdi:train-car')
                    if int(self._direction) == 0 or int(direction) \
                            == int(self._direction):
                        if self._lines is None or linenumber \
                                in self._lines:
                            diff = self.parseDepartureTime(displaytime)
                            if diff < self._timewindow:
                                departures.append({
                                    'line': linenumber,
                                    'direction': direction,
                                    'departure': displaytime,
                                    'destination': destination,
                                    'time': diff,
                                    'expected': expected,
                                    'type': traffictype,
                                    'icon': icon,
                                    })

            self._departure_table = sorted(departures,
                                           key=lambda k: k['time'])

            _LOGGER.info("RI4 update completed for %s...", self._name)

    def _update_si2(self):
        errorOccured = False
        _LOGGER.info("Starting to update SI2 for %s...", self._name)

        cacheage = self._hass.data[DOMAIN][self._si2datakey]
        if not cacheage or now(self._hass.config.time_zone) \
                - self._interval > cacheage or not self._minimization:

            try:
                deviationdata = self._si2api.request()
                deviationdata = deviationdata['ResponseData']

                self.putCache(self._si2datakey, deviationdata)
                self._hass.data[DOMAIN][self._si2datakey] = \
                    now(self._hass.config.time_zone)

                _LOGGER.info('Updated cache for %s...', self._name)

            except HASL_Error as e:
                _LOGGER.error("A communication error occured while"
                              "updating SI2 sensor: %s", e.details)
                errorOccured = True

            except Exception as e:
                _LOGGER.error("A error occured while"
                              "updating SI2 sensor: %s", e)
                errorOccured = True

        else:
            try:
                deviationdata = self.getCache(self._si2datakey)

                _LOGGER.info("Reusing data from cache for %s...",
                             self._name)

            except Exception as e:
                _LOGGER.error("A error occured while retreiving"
                              "cached SI2 sensor: %s", e.details)
                errorOccured = True

        if not errorOccured:
            deviations = []
            for (idx, value) in enumerate(deviationdata):
                deviations.append({
                    'updated': value['Updated'],
                    'title': value['Header'],
                    'fromDate': value['FromDateTime'],
                    'toDate': value['UpToDateTime'],
                    'details': value['Details'],
                    'sortOrder': value['SortOrder'],
                    })

            self._deviations_table = \
                sorted(deviations, key=lambda k: k['sortOrder'])

            _LOGGER.info("SI2 update completed for %s...", self._name)
