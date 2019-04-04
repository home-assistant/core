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

REQUIREMENTS = ['py17track==2.2.2']
_LOGGER = logging.getLogger(__name__)

ATTR_DESTINATION_COUNTRY = 'destination_country'
ATTR_FRIENDLY_NAME = 'friendly_name'
ATTR_INFO_TEXT = 'info_text'
ATTR_ORIGIN_COUNTRY = 'origin_country'
ATTR_PACKAGES = 'packages'
ATTR_PACKAGE_TYPE = 'package_type'
ATTR_STATUS = 'status'
ATTR_TRACKING_INFO_LANGUAGE = 'tracking_info_language'
ATTR_TRACKING_NUMBER = 'tracking_number'

CONF_SHOW_ARCHIVED = 'show_archived'
CONF_SHOW_DELIVERED = 'show_delivered'

DATA_PACKAGES = 'package_data'
DATA_SUMMARY = 'summary_data'

DEFAULT_ATTRIBUTION = 'Data provided by 17track.net'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

NOTIFICATION_DELIVERED_ID_SCAFFOLD = 'package_delivered_{0}'
NOTIFICATION_DELIVERED_TITLE = 'Package Delivered'
NOTIFICATION_DELIVERED_URL_SCAFFOLD = 'https://t.17track.net/track#nums={0}'

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

        if not login_result:
            _LOGGER.error('Invalid username and password provided')
            return
    except SeventeenTrackError as err:
        _LOGGER.error('There was an error while logging in: %s', err)
        return

    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    data = SeventeenTrackData(
        client, async_add_entities, scan_interval, config[CONF_SHOW_ARCHIVED],
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

    def __init__(self, data, status, initial_state):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._data = data
        self._state = initial_state
        self._status = status

    @property
    def available(self):
        """Return whether the entity is available."""
        return self._state is not None

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
        return 'Seventeentrack Packages {0}'.format(self._status)

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return 'summary_{0}_{1}'.format(
            self._data.account_id, slugify(self._status))

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return 'packages'

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()

        package_data = []
        for package in self._data.packages:
            if package.status != self._status:
                continue

            package_data.append({
                ATTR_FRIENDLY_NAME: package.friendly_name,
                ATTR_INFO_TEXT: package.info_text,
                ATTR_STATUS: package.status,
                ATTR_TRACKING_NUMBER: package.tracking_number,
            })

        if package_data:
            self._attrs[ATTR_PACKAGES] = package_data

        self._state = self._data.summary.get(self._status)


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
            ATTR_TRACKING_NUMBER: package.tracking_number,
        }
        self._data = data
        self._friendly_name = package.friendly_name
        self._state = package.status
        self._tracking_number = package.tracking_number

    @property
    def available(self):
        """Return whether the entity is available."""
        return bool([
            p for p in self._data.packages
            if p.tracking_number == self._tracking_number
        ])

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
        name = self._friendly_name
        if not name:
            name = self._tracking_number
        return 'Seventeentrack Package: {0}'.format(name)

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return 'package_{0}_{1}'.format(
            self._data.account_id, self._tracking_number)

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()

        if not self._data.packages:
            return

        try:
            package = next((
                p for p in self._data.packages
                if p.tracking_number == self._tracking_number))
        except StopIteration:
            # If the package no longer exists in the data, log a message and
            # delete this entity:
            _LOGGER.info(
                'Deleting entity for stale package: %s', self._tracking_number)
            self.hass.async_create_task(self.async_remove())
            return

        # If the user has elected to not see delivered packages and one gets
        # delivered, post a notification and delete the entity:
        if package.status == VALUE_DELIVERED and not self._data.show_delivered:
            _LOGGER.info('Package delivered: %s', self._tracking_number)
            self.hass.components.persistent_notification.create(
                'Package Delivered: {0}<br />'
                'Visit 17.track for more infomation: {1}'
                ''.format(
                    self._tracking_number,
                    NOTIFICATION_DELIVERED_URL_SCAFFOLD.format(
                        self._tracking_number)),
                title=NOTIFICATION_DELIVERED_TITLE,
                notification_id=NOTIFICATION_DELIVERED_ID_SCAFFOLD.format(
                    self._tracking_number))
            self.hass.async_create_task(self.async_remove())
            return

        self._attrs.update({
            ATTR_INFO_TEXT: package.info_text,
            ATTR_LOCATION: package.location,
        })
        self._state = package.status


class SeventeenTrackData:
    """Define a data handler for 17track.net."""

    def __init__(
            self, client, async_add_entities, scan_interval, show_archived,
            show_delivered):
        """Initialize."""
        self._async_add_entities = async_add_entities
        self._client = client
        self._scan_interval = scan_interval
        self._show_archived = show_archived
        self.account_id = client.profile.account_id
        self.packages = []
        self.show_delivered = show_delivered
        self.summary = {}

        self.async_update = Throttle(self._scan_interval)(self._async_update)

    async def _async_update(self):
        """Get updated data from 17track.net."""
        from py17track.errors import SeventeenTrackError

        try:
            packages = await self._client.profile.packages(
                show_archived=self._show_archived)
            _LOGGER.debug('New package data received: %s', packages)

            if not self.show_delivered:
                packages = [p for p in packages if p.status != VALUE_DELIVERED]

            # Add new packages:
            to_add = set(packages) - set(self.packages)
            if self.packages and to_add:
                self._async_add_entities([
                    SeventeenTrackPackageSensor(self, package)
                    for package in to_add
                ], True)

            self.packages = packages
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
