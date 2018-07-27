"""
Support for Pollen.com allergen and cold/flu sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pollen/
"""
import logging
from datetime import timedelta
from statistics import mean

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_STATE, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pypollencom==2.1.0']
_LOGGER = logging.getLogger(__name__)

ATTR_ALLERGEN_GENUS = 'allergen_genus'
ATTR_ALLERGEN_NAME = 'allergen_name'
ATTR_ALLERGEN_TYPE = 'allergen_type'
ATTR_CITY = 'city'
ATTR_OUTLOOK = 'outlook'
ATTR_RATING = 'rating'
ATTR_SEASON = 'season'
ATTR_TREND = 'trend'
ATTR_ZIP_CODE = 'zip_code'

CONF_ZIP_CODE = 'zip_code'

DEFAULT_ATTRIBUTION = 'Data provided by IQVIA™'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

TYPE_ALLERGY_FORECAST = 'allergy_average_forecasted'
TYPE_ALLERGY_HISTORIC = 'allergy_average_historical'
TYPE_ALLERGY_INDEX = 'allergy_index'
TYPE_ALLERGY_OUTLOOK = 'allergy_outlook'
TYPE_ALLERGY_TODAY = 'allergy_index_today'
TYPE_ALLERGY_TOMORROW = 'allergy_index_tomorrow'
TYPE_ALLERGY_YESTERDAY = 'allergy_index_yesterday'
TYPE_DISEASE_FORECAST = 'disease_average_forecasted'

SENSORS = {
    TYPE_ALLERGY_FORECAST: (
        'Allergy Index: Forecasted Average', None, 'mdi:flower', 'index'),
    TYPE_ALLERGY_HISTORIC: (
        'Allergy Index: Historical Average', None, 'mdi:flower', 'index'),
    TYPE_ALLERGY_TODAY: (
        'Allergy Index: Today', TYPE_ALLERGY_INDEX, 'mdi:flower', 'index'),
    TYPE_ALLERGY_TOMORROW: (
        'Allergy Index: Tomorrow', TYPE_ALLERGY_INDEX, 'mdi:flower', 'index'),
    TYPE_ALLERGY_YESTERDAY: (
        'Allergy Index: Yesterday', TYPE_ALLERGY_INDEX, 'mdi:flower', 'index'),
    TYPE_DISEASE_FORECAST: (
        'Cold & Flu: Forecasted Average', None, 'mdi:snowflake', 'index')
}

RATING_MAPPING = [{
    'label': 'Low',
    'minimum': 0.0,
    'maximum': 2.4
}, {
    'label': 'Low/Medium',
    'minimum': 2.5,
    'maximum': 4.8
}, {
    'label': 'Medium',
    'minimum': 4.9,
    'maximum': 7.2
}, {
    'label': 'Medium/High',
    'minimum': 7.3,
    'maximum': 9.6
}, {
    'label': 'High',
    'minimum': 9.7,
    'maximum': 12
}]

TREND_FLAT = 'Flat'
TREND_INCREASING = 'Increasing'
TREND_SUBSIDING = 'Subsiding'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIP_CODE): str,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pypollencom import Client

    websession = aiohttp_client.async_get_clientsession(hass)

    data = PollenComData(
        Client(config[CONF_ZIP_CODE], websession),
        config[CONF_MONITORED_CONDITIONS])

    await data.async_update()

    sensors = []
    for kind in config[CONF_MONITORED_CONDITIONS]:
        name, category, icon, unit = SENSORS[kind]
        sensors.append(
            PollencomSensor(
                data, config[CONF_ZIP_CODE], kind, category, name, icon, unit))

    async_add_devices(sensors, True)


def calculate_average_rating(indices):
    """Calculate the human-friendly historical allergy average."""
    ratings = list(
        r['label'] for n in indices for r in RATING_MAPPING
        if r['minimum'] <= n <= r['maximum'])
    return max(set(ratings), key=ratings.count)


class PollencomSensor(Entity):
    """Define a Pollen.com sensor."""

    def __init__(self, pollencom, zip_code, kind, category, name, icon, unit):
        """Initialize the sensor."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._category = category
        self._icon = icon
        self._name = name
        self._state = None
        self._type = kind
        self._unit = unit
        self._zip_code = zip_code
        self.pollencom = pollencom

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(
            self.pollencom.data.get(self._type)
            or self.pollencom.data.get(self._category))

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
        return '{0}_{1}'.format(self._zip_code, self._type)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_update(self):
        """Update the sensor."""
        await self.pollencom.async_update()
        if not self.pollencom.data:
            return

        if self._category:
            data = self.pollencom.data[self._category].get('Location')
        else:
            data = self.pollencom.data[self._type].get('Location')

        if not data:
            return

        indices = [p['Index'] for p in data['periods']]
        average = round(mean(indices), 1)
        [rating] = [
            i['label'] for i in RATING_MAPPING
            if i['minimum'] <= average <= i['maximum']
        ]
        slope = (data['periods'][-1]['Index'] - data['periods'][-2]['Index'])
        trend = TREND_FLAT
        if slope > 0:
            trend = TREND_INCREASING
        elif slope < 0:
            trend = TREND_SUBSIDING

        if self._type == TYPE_ALLERGY_FORECAST:
            outlook = self.pollencom.data[TYPE_ALLERGY_OUTLOOK]

            self._attrs.update({
                ATTR_CITY: data['City'].title(),
                ATTR_OUTLOOK: outlook['Outlook'],
                ATTR_RATING: rating,
                ATTR_SEASON: outlook['Season'].title(),
                ATTR_STATE: data['State'],
                ATTR_TREND: outlook['Trend'].title(),
                ATTR_ZIP_CODE: data['ZIP']
            })
            self._state = average
        elif self._type == TYPE_ALLERGY_HISTORIC:
            self._attrs.update({
                ATTR_CITY: data['City'].title(),
                ATTR_RATING: calculate_average_rating(indices),
                ATTR_STATE: data['State'],
                ATTR_TREND: trend,
                ATTR_ZIP_CODE: data['ZIP']
            })
            self._state = average
        elif self._type in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                            TYPE_ALLERGY_YESTERDAY):
            key = self._type.split('_')[-1].title()
            [period] = [p for p in data['periods'] if p['Type'] == key]
            [rating] = [
                i['label'] for i in RATING_MAPPING
                if i['minimum'] <= period['Index'] <= i['maximum']
            ]

            for idx, attrs in enumerate(period['Triggers']):
                index = idx + 1
                self._attrs.update({
                    '{0}_{1}'.format(ATTR_ALLERGEN_GENUS, index):
                        attrs['Genus'],
                    '{0}_{1}'.format(ATTR_ALLERGEN_NAME, index):
                        attrs['Name'],
                    '{0}_{1}'.format(ATTR_ALLERGEN_TYPE, index):
                        attrs['PlantType'],
                })

            self._attrs.update({
                ATTR_CITY: data['City'].title(),
                ATTR_RATING: rating,
                ATTR_STATE: data['State'],
                ATTR_ZIP_CODE: data['ZIP']
            })
            self._state = period['Index']
        elif self._type == TYPE_DISEASE_FORECAST:
            self._attrs.update({
                ATTR_CITY: data['City'].title(),
                ATTR_RATING: rating,
                ATTR_STATE: data['State'],
                ATTR_TREND: trend,
                ATTR_ZIP_CODE: data['ZIP']
            })
            self._state = average


class PollenComData(object):
    """Define a data object to retrieve info from Pollen.com."""

    def __init__(self, client, sensor_types):
        """Initialize."""
        self._client = client
        self._sensor_types = sensor_types
        self.data = {}

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Update Pollen.com data."""
        from pypollencom.errors import InvalidZipError, PollenComError

        # Pollen.com requires a bit more complicated error handling, given that
        # it sometimes has parts (but not the whole thing) go down:
        #
        # 1. If `InvalidZipError` is thrown, quit everything immediately.
        # 2. If an individual request throws any other error, try the others.

        try:
            if TYPE_ALLERGY_FORECAST in self._sensor_types:
                try:
                    data = await self._client.allergens.extended()
                    self.data[TYPE_ALLERGY_FORECAST] = data
                except PollenComError as err:
                    _LOGGER.error('Unable to get allergy forecast: %s', err)
                    self.data[TYPE_ALLERGY_FORECAST] = {}

                try:
                    data = await self._client.allergens.outlook()
                    self.data[TYPE_ALLERGY_OUTLOOK] = data
                except PollenComError as err:
                    _LOGGER.error('Unable to get allergy outlook: %s', err)
                    self.data[TYPE_ALLERGY_OUTLOOK] = {}

            if TYPE_ALLERGY_HISTORIC in self._sensor_types:
                try:
                    data = await self._client.allergens.historic()
                    self.data[TYPE_ALLERGY_HISTORIC] = data
                except PollenComError as err:
                    _LOGGER.error('Unable to get allergy history: %s', err)
                    self.data[TYPE_ALLERGY_HISTORIC] = {}

            if all(s in self._sensor_types
                   for s in [TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                             TYPE_ALLERGY_YESTERDAY]):
                try:
                    data = await self._client.allergens.current()
                    self.data[TYPE_ALLERGY_INDEX] = data
                except PollenComError as err:
                    _LOGGER.error('Unable to get current allergies: %s', err)
                    self.data[TYPE_ALLERGY_TODAY] = {}

            if TYPE_DISEASE_FORECAST in self._sensor_types:
                try:
                    data = await self._client.disease.extended()
                    self.data[TYPE_DISEASE_FORECAST] = data
                except PollenComError as err:
                    _LOGGER.error('Unable to get disease forecast: %s', err)
                    self.data[TYPE_DISEASE_FORECAST] = {}

            _LOGGER.debug('New data retrieved: %s', self.data)
        except InvalidZipError:
            _LOGGER.error(
                'Cannot retrieve data for ZIP code: %s', self._client.zip_code)
            self.data = {}
