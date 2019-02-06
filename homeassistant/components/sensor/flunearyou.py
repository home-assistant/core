"""
Support for user- and CDC-based flu info sensors from Flu Near You.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.flunearyou/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_STATE, CONF_LATITUDE, CONF_MONITORED_CONDITIONS,
    CONF_LONGITUDE)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyflunearyou==1.0.1']
_LOGGER = logging.getLogger(__name__)

ATTR_CITY = 'city'
ATTR_REPORTED_DATE = 'reported_date'
ATTR_REPORTED_LATITUDE = 'reported_latitude'
ATTR_REPORTED_LONGITUDE = 'reported_longitude'
ATTR_STATE_REPORTS_LAST_WEEK = 'state_reports_last_week'
ATTR_STATE_REPORTS_THIS_WEEK = 'state_reports_this_week'
ATTR_ZIP_CODE = 'zip_code'

DEFAULT_ATTRIBUTION = 'Data provided by Flu Near You'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
SCAN_INTERVAL = timedelta(minutes=30)

CATEGORY_CDC_REPORT = 'cdc_report'
CATEGORY_USER_REPORT = 'user_report'

TYPE_CDC_LEVEL = 'level'
TYPE_CDC_LEVEL2 = 'level2'
TYPE_USER_CHICK = 'chick'
TYPE_USER_DENGUE = 'dengue'
TYPE_USER_FLU = 'flu'
TYPE_USER_LEPTO = 'lepto'
TYPE_USER_NO_SYMPTOMS = 'none'
TYPE_USER_SYMPTOMS = 'symptoms'
TYPE_USER_TOTAL = 'total'

EXTENDED_TYPE_MAPPING = {
    TYPE_USER_FLU: 'ili',
    TYPE_USER_NO_SYMPTOMS: 'no_symptoms',
    TYPE_USER_TOTAL: 'total_surveys',
}

SENSORS = {
    CATEGORY_CDC_REPORT: [
        (TYPE_CDC_LEVEL, 'CDC Level', 'mdi:biohazard', None),
        (TYPE_CDC_LEVEL2, 'CDC Level 2', 'mdi:biohazard', None),
    ],
    CATEGORY_USER_REPORT: [
        (TYPE_USER_CHICK, 'Avian Flu Symptoms', 'mdi:alert', 'reports'),
        (TYPE_USER_DENGUE, 'Dengue Fever Symptoms', 'mdi:alert', 'reports'),
        (TYPE_USER_FLU, 'Flu Symptoms', 'mdi:alert', 'reports'),
        (TYPE_USER_LEPTO, 'Leptospirosis Symptoms', 'mdi:alert', 'reports'),
        (TYPE_USER_NO_SYMPTOMS, 'No Symptoms', 'mdi:alert', 'reports'),
        (TYPE_USER_SYMPTOMS, 'Flu-like Symptoms', 'mdi:alert', 'reports'),
        (TYPE_USER_TOTAL, 'Total Symptoms', 'mdi:alert', 'reports'),
    ]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pyflunearyou import Client

    websession = aiohttp_client.async_get_clientsession(hass)

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    fny = FluNearYouData(
        Client(websession), latitude, longitude,
        config[CONF_MONITORED_CONDITIONS])
    await fny.async_update()

    sensors = [
        FluNearYouSensor(fny, kind, name, category, icon, unit)
        for category in config[CONF_MONITORED_CONDITIONS]
        for kind, name, icon, unit in SENSORS[category]
    ]

    async_add_entities(sensors, True)


class FluNearYouSensor(Entity):
    """Define a base Flu Near You sensor."""

    def __init__(self, fny, kind, name, category, icon, unit):
        """Initialize the sensor."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._category = category
        self._icon = icon
        self._kind = kind
        self._name = name
        self._state = None
        self._unit = unit
        self.fny = fny

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.fny.data[self._category])

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

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
        return '{0},{1}_{2}'.format(
            self.fny.latitude, self.fny.longitude, self._kind)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_update(self):
        """Update the sensor."""
        await self.fny.async_update()

        cdc_data = self.fny.data.get(CATEGORY_CDC_REPORT)
        user_data = self.fny.data.get(CATEGORY_USER_REPORT)

        if self._category == CATEGORY_CDC_REPORT and cdc_data:
            self._attrs.update({
                ATTR_REPORTED_DATE: cdc_data['week_date'],
                ATTR_STATE: cdc_data['name'],
            })
            self._state = cdc_data[self._kind]
        elif self._category == CATEGORY_USER_REPORT and user_data:
            self._attrs.update({
                ATTR_CITY: user_data['local']['city'].split('(')[0],
                ATTR_REPORTED_LATITUDE: user_data['local']['latitude'],
                ATTR_REPORTED_LONGITUDE: user_data['local']['longitude'],
                ATTR_STATE: user_data['state']['name'],
                ATTR_ZIP_CODE: user_data['local']['zip'],
            })

            if self._kind in user_data['state']['data']:
                states_key = self._kind
            elif self._kind in EXTENDED_TYPE_MAPPING:
                states_key = EXTENDED_TYPE_MAPPING[self._kind]

            self._attrs[ATTR_STATE_REPORTS_THIS_WEEK] = user_data['state'][
                'data'][states_key]
            self._attrs[ATTR_STATE_REPORTS_LAST_WEEK] = user_data['state'][
                'last_week_data'][states_key]

            if self._kind == TYPE_USER_TOTAL:
                self._state = sum(
                    v for k, v in user_data['local'].items() if k in (
                        TYPE_USER_CHICK, TYPE_USER_DENGUE, TYPE_USER_FLU,
                        TYPE_USER_LEPTO, TYPE_USER_SYMPTOMS))
            else:
                self._state = user_data['local'][self._kind]


class FluNearYouData:
    """Define a data object to retrieve info from Flu Near You."""

    def __init__(self, client, latitude, longitude, sensor_types):
        """Initialize."""
        self._client = client
        self._sensor_types = sensor_types
        self.data = {}
        self.latitude = latitude
        self.longitude = longitude

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update Flu Near You data."""
        from pyflunearyou.errors import FluNearYouError

        for key, method in [(CATEGORY_CDC_REPORT,
                             self._client.cdc_reports.status_by_coordinates),
                            (CATEGORY_USER_REPORT,
                             self._client.user_reports.status_by_coordinates)]:
            if key in self._sensor_types:
                try:
                    self.data[key] = await method(
                        self.latitude, self.longitude)
                except FluNearYouError as err:
                    _LOGGER.error(
                        'There was an error with "%s" data: %s', key, err)
                    self.data[key] = {}

        _LOGGER.debug('New data stored: %s', self.data)
