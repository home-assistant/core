"""
Support for package tracking sensors from 17track.net.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.seventeentrack/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_LOCATION, CONF_PASSWORD, CONF_SCAN_INTERVAL,
    CONF_USERNAME)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, slugify

REQUIREMENTS = ['py17track==2.0.1']
_LOGGER = logging.getLogger(__name__)

ATTR_DESTINATION_COUNTRY = 'destination_country'
ATTR_INFO_TEXT = 'info_text'
ATTR_ORIGIN_COUNTRY = 'origin_country'
ATTR_PACKAGE_TYPE = 'package_type'
ATTR_TRACKING_INFO_LANGUAGE = 'tracking_info_language'

CONF_SHOW_ARCHIVED = 'show_archived'
CONF_SHOW_DELIVERED = 'show_delivered'

DATA_PACKAGES = 'package_data'
DATA_SUMMARY = 'summary_data'

DEFAULT_ATTRIBUTION = 'Data provided by 17track.net'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

VALUE_DELIVERED = 'Delivered'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SHOW_ARCHIVED, default=False): cv.boolean,
    vol.Optional(CONF_SHOW_DELIVERED, default=False): cv.boolean,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Configure the platform and add the sensors."""
    from py17track import Client
    from py17track.errors import SeventeenTrackError

    websession = aiohttp_client.async_get_clientsession(hass)

    client = Client(websession)

    try:
        login_result = await client.profile.login(
            config[CONF_USERNAME], config[CONF_PASSWORD])

        if login_result is False:
            _LOGGER.error('Invalid username and password provided')
            return False
    except SeventeenTrackError as err:
        _LOGGER.error('There was an error while logging in: %s', err)
        return False

    if CONF_SCAN_INTERVAL in config:
        scan_interval = config[CONF_SCAN_INTERVAL]
    else:
        scan_interval = DEFAULT_SCAN_INTERVAL

    data = SeventeenTrackData(
        client, scan_interval, config[CONF_SHOW_ARCHIVED],
        config[CONF_SHOW_DELIVERED])
    await data.async_update()

    sensors = []

    for status, quantity in data.summary.items():
        sensors.append(SeventeenTrackSummarySensor(data, status, quantity))

    for package in data.packages:
        sensors.append(SeventeenTrackPackageSensor(data, package))

    async_add_entities(sensors, True)


class SeventeenTrackSummarySensor(Entity):
    """Define a summary sensor."""

    def __init__(self, data, name, initial_state):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._data = data
        self._name = name
        self._state = initial_state

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:package'

    @property
    def name(self):
        """Return the name."""
        return 'Packages {0}'.format(self._name)

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}'.format(self._data.account_id, slugify(self._name))

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._state == 1:
            return 'package'
        return 'packages'

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()

        self._state = self._data.summary[self._name]


class SeventeenTrackPackageSensor(Entity):
    """Define an individual package sensor."""

    def __init__(self, data, package):
        """Initialize."""
        self._attrs = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_DESTINATION_COUNTRY: package.destination_country,
            ATTR_INFO_TEXT: package.info_text,
            ATTR_LOCATION: package.location,
            ATTR_ORIGIN_COUNTRY: package.origin_country,
            ATTR_PACKAGE_TYPE: package.package_type,
            ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
        }
        self._data = data
        self._name = package.tracking_number
        self._state = package.status

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:package'

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}'.format(self._data.account_id, self._name)

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()
        [package] = [
            p for p in self._data.packages if p.tracking_number == self._name
        ]

        self._attrs.update({
            ATTR_INFO_TEXT: package.info_text,
            ATTR_LOCATION: package.location,
        })
        self._state = package.status


class SeventeenTrackData:
    """Define a data handler for 17track.net."""

    def __init__(self, client, scan_interval, show_archived, show_delivered):
        """Initialize."""
        self._client = client
        self._scan_interval = scan_interval
        self._show_archived = show_archived
        self._show_delivered = show_delivered
        self.account_id = client.profile.account_id
        self.packages = []
        self.summary = {}

        self.async_update = Throttle(self._scan_interval)(self._async_update)

    async def _async_update(self):
        """Get updated data from 17track.net."""
        from py17track.errors import SeventeenTrackError

        try:
            packages = await self._client.profile.packages(
                show_archived=self._show_archived)
            _LOGGER.debug('New package data received: %s', packages)

            if self._show_delivered:
                self.packages = packages
            else:
                self.packages = [
                    p for p in packages if p.status != VALUE_DELIVERED
                ]
        except SeventeenTrackError as err:
            _LOGGER.error('There was an error retrieving packages: %s', err)
            self.packages = []

        try:
            self.summary = await self._client.profile.summary(
                show_archived=self._show_archived)
            _LOGGER.debug('New summary data received: %s', self.summary)
        except SeventeenTrackError as err:
            _LOGGER.error('There was an error retrieving the summary: %s', err)
            self.summary = {}
