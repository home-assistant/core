"""
Support for Sonarr.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sonarr/
"""
import logging
import time
from datetime import datetime

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_MONITORED_CONDITIONS, CONF_SSL)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_DAYS = 'days'
CONF_INCLUDED = 'include_paths'
CONF_UNIT = 'unit'
CONF_URLBASE = 'urlbase'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8989
DEFAULT_URLBASE = ''
DEFAULT_DAYS = '1'
DEFAULT_UNIT = 'GB'

SENSOR_TYPES = {
    'diskspace': ['Disk Space', 'GB', 'mdi:harddisk'],
    'queue': ['Queue', 'Episodes', 'mdi:download'],
    'upcoming': ['Upcoming', 'Episodes', 'mdi:television'],
    'wanted': ['Wanted', 'Episodes', 'mdi:television'],
    'series': ['Series', 'Shows', 'mdi:television'],
    'commands': ['Commands', 'Commands', 'mdi:code-braces'],
    'status': ['Status', 'Status', 'mdi:information']
}

ENDPOINTS = {
    'diskspace': 'http{0}://{1}:{2}/{3}api/diskspace',
    'queue': 'http{0}://{1}:{2}/{3}api/queue',
    'upcoming':
        'http{0}://{1}:{2}/{3}api/calendar?start={4}&end={5}',
    'wanted': 'http{0}://{1}:{2}/{3}api/wanted/missing',
    'series': 'http{0}://{1}:{2}/{3}api/series',
    'commands': 'http{0}://{1}:{2}/{3}api/command',
    'status': 'http{0}://{1}:{2}/{3}api/system/status'
}

# Support to Yottabytes for the future, why not
BYTE_SIZES = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_INCLUDED, default=[]): cv.ensure_list,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['upcoming']):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): vol.In(BYTE_SIZES),
    vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sonarr platform."""
    conditions = config.get(CONF_MONITORED_CONDITIONS)
    add_entities(
        [SonarrSensor(hass, config, sensor) for sensor in conditions], True)


class SonarrSensor(Entity):
    """Implementation of the Sonarr sensor."""

    def __init__(self, hass, conf, sensor_type):
        """Create Sonarr entity."""
        from pytz import timezone
        self.conf = conf
        self.host = conf.get(CONF_HOST)
        self.port = conf.get(CONF_PORT)
        self.urlbase = conf.get(CONF_URLBASE)
        if self.urlbase:
            self.urlbase = "{}/".format(self.urlbase.strip('/'))
        self.apikey = conf.get(CONF_API_KEY)
        self.included = conf.get(CONF_INCLUDED)
        self.days = int(conf.get(CONF_DAYS))
        self.ssl = 's' if conf.get(CONF_SSL) else ''
        self._state = None
        self.data = []
        self._tz = timezone(str(hass.config.time_zone))
        self.type = sensor_type
        self._name = SENSOR_TYPES[self.type][0]
        if self.type == 'diskspace':
            self._unit = conf.get(CONF_UNIT)
        else:
            self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format('Sonarr', self._name)

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def available(self):
        """Return sensor availability."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        if self.type == 'upcoming':
            for show in self.data:
                attributes[show['series']['title']] = 'S{:02d}E{:02d}'.format(
                    show['seasonNumber'], show['episodeNumber'])
        elif self.type == 'queue':
            for show in self.data:
                remaining = (1 if show['size'] == 0
                             else show['sizeleft']/show['size'])
                attributes[show['series']['title'] + ' S{:02d}E{:02d}'.format(
                    show['episode']['seasonNumber'],
                    show['episode']['episodeNumber']
                )] = '{:.2f}%'.format(100*(1-(remaining)))
        elif self.type == 'wanted':
            for show in self.data:
                attributes[show['series']['title'] + ' S{:02d}E{:02d}'.format(
                    show['seasonNumber'], show['episodeNumber']
                )] = show['airDate']
        elif self.type == 'commands':
            for command in self.data:
                attributes[command['name']] = command['state']
        elif self.type == 'diskspace':
            for data in self.data:
                attributes[data['path']] = '{:.2f}/{:.2f}{} ({:.2f}%)'.format(
                    to_unit(data['freeSpace'], self._unit),
                    to_unit(data['totalSpace'], self._unit),
                    self._unit, (
                        to_unit(data['freeSpace'], self._unit) /
                        to_unit(data['totalSpace'], self._unit) * 100
                    )
                )
        elif self.type == 'series':
            for show in self.data:
                if 'episodeFileCount' not in show \
                        or 'episodeCount' not in show:
                    attributes[show['title']] = 'N/A'
                else:
                    attributes[show['title']] = '{}/{} Episodes'.format(
                        show['episodeFileCount'], show['episodeCount'])
        elif self.type == 'status':
            attributes = self.data
        return attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    def update(self):
        """Update the data for the sensor."""
        start = get_date(self._tz)
        end = get_date(self._tz, self.days)
        try:
            res = requests.get(
                ENDPOINTS[self.type].format(
                    self.ssl, self.host, self.port,
                    self.urlbase, start, end),
                headers={'X-Api-Key': self.apikey},
                timeout=10)
        except OSError:
            _LOGGER.warning("Host %s is not available", self.host)
            self._available = False
            self._state = None
            return

        if res.status_code == 200:
            if self.type in ['upcoming', 'queue', 'series', 'commands']:
                if self.days == 1 and self.type == 'upcoming':
                    # Sonarr API returns an empty array if start and end dates
                    # are the same, so we need to filter to just today
                    self.data = list(
                        filter(
                            lambda x: x['airDate'] == str(start),
                            res.json()
                        )
                    )
                else:
                    self.data = res.json()
                self._state = len(self.data)
            elif self.type == 'wanted':
                data = res.json()
                res = requests.get(
                    '{}?pageSize={}'.format(
                        ENDPOINTS[self.type].format(
                            self.ssl, self.host, self.port, self.urlbase),
                        data['totalRecords']),
                    headers={'X-Api-Key': self.apikey},
                    timeout=10)
                self.data = res.json()['records']
                self._state = len(self.data)
            elif self.type == 'diskspace':
                # If included paths are not provided, use all data
                if self.included == []:
                    self.data = res.json()
                else:
                    # Filter to only show lists that are included
                    self.data = list(
                        filter(
                            lambda x: x['path'] in self.included,
                            res.json()
                        )
                    )
                self._state = '{:.2f}'.format(
                    to_unit(
                        sum([data['freeSpace'] for data in self.data]),
                        self._unit
                    )
                )
            elif self.type == 'status':
                self.data = res.json()
                self._state = self.data['version']
            self._available = True


def get_date(zone, offset=0):
    """Get date based on timezone and offset of days."""
    day = 60 * 60 * 24
    return datetime.date(
        datetime.fromtimestamp(time.time() + day*offset, tz=zone)
    )


def to_unit(value, unit):
    """Convert bytes to give unit."""
    return value / 1024**BYTE_SIZES.index(unit)
