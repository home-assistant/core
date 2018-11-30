"""
Support for Pollen.com allergen and cold/flu sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pollen/
"""
from datetime import timedelta
import logging
from statistics import mean

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_STATE, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['numpy==1.15.4', 'pypollencom==2.2.2']

_LOGGER = logging.getLogger(__name__)

ATTR_ALLERGEN_AMOUNT = 'allergen_amount'
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
TYPE_ASTHMA_FORECAST = 'asthma_average_forecasted'
TYPE_ASTHMA_HISTORIC = 'asthma_average_historical'
TYPE_ASTHMA_INDEX = 'asthma_index'
TYPE_ASTHMA_TODAY = 'asthma_index_today'
TYPE_ASTHMA_TOMORROW = 'asthma_index_tomorrow'
TYPE_ASTHMA_YESTERDAY = 'asthma_index_yesterday'
TYPE_DISEASE_FORECAST = 'disease_average_forecasted'

SENSORS = {
    TYPE_ALLERGY_FORECAST: (
        'ForecastSensor', 'Allergy Index: Forecasted Average', 'mdi:flower'),
    TYPE_ALLERGY_HISTORIC: (
        'HistoricalSensor', 'Allergy Index: Historical Average', 'mdi:flower'),
    TYPE_ALLERGY_TODAY: ('IndexSensor', 'Allergy Index: Today', 'mdi:flower'),
    TYPE_ALLERGY_TOMORROW: (
        'IndexSensor', 'Allergy Index: Tomorrow', 'mdi:flower'),
    TYPE_ALLERGY_YESTERDAY: (
        'IndexSensor', 'Allergy Index: Yesterday', 'mdi:flower'),
    TYPE_ASTHMA_TODAY: ('IndexSensor', 'Asthma Index: Today', 'mdi:flower'),
    TYPE_ASTHMA_TOMORROW: (
        'IndexSensor', 'Asthma Index: Tomorrow', 'mdi:flower'),
    TYPE_ASTHMA_YESTERDAY: (
        'IndexSensor', 'Asthma Index: Yesterday', 'mdi:flower'),
    TYPE_ASTHMA_FORECAST: (
        'ForecastSensor', 'Asthma Index: Forecasted Average', 'mdi:flower'),
    TYPE_ASTHMA_HISTORIC: (
        'HistoricalSensor', 'Asthma Index: Historical Average', 'mdi:flower'),
    TYPE_DISEASE_FORECAST: (
        'ForecastSensor', 'Cold & Flu: Forecasted Average', 'mdi:snowflake')
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

TREND_INCREASING = 'Increasing'
TREND_SUBSIDING = 'Subsiding'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIP_CODE):
        str,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pypollencom import Client

    websession = aiohttp_client.async_get_clientsession(hass)

    pollen = PollenComData(
        Client(config[CONF_ZIP_CODE], websession),
        config[CONF_MONITORED_CONDITIONS])

    await pollen.async_update()

    sensors = []
    for kind in config[CONF_MONITORED_CONDITIONS]:
        sensor_class, name, icon = SENSORS[kind]
        sensors.append(
            globals()[sensor_class](
                pollen, kind, name, icon, config[CONF_ZIP_CODE]))

    async_add_entities(sensors, True)


def calculate_average_rating(indices):
    """Calculate the human-friendly historical allergy average."""
    ratings = list(
        r['label'] for n in indices for r in RATING_MAPPING
        if r['minimum'] <= n <= r['maximum'])
    return max(set(ratings), key=ratings.count)


def calculate_trend(indices):
    """Calculate the "moving average" of a set of indices."""
    import numpy as np

    def moving_average(data, samples):
        """Determine the "moving average" (http://tinyurl.com/yaereb3c)."""
        ret = np.cumsum(data, dtype=float)
        ret[samples:] = ret[samples:] - ret[:-samples]
        return ret[samples - 1:] / samples

    increasing = np.all(np.diff(moving_average(np.array(indices), 4)) > 0)

    if increasing:
        return TREND_INCREASING
    return TREND_SUBSIDING


class BaseSensor(Entity):
    """Define a base Pollen.com sensor."""

    def __init__(self, pollen, kind, name, icon, zip_code):
        """Initialize the sensor."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._kind = kind
        self._name = name
        self._state = None
        self._zip_code = zip_code
        self.pollen = pollen

    @property
    def available(self):
        """Return True if entity is available."""
        if self._kind in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                          TYPE_ALLERGY_YESTERDAY):
            return bool(self.pollen.data[TYPE_ALLERGY_INDEX])

        if self._kind in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                          TYPE_ASTHMA_YESTERDAY):
            return bool(self.pollen.data[TYPE_ASTHMA_INDEX])

        return bool(self.pollen.data[self._kind])

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
        return '{0}_{1}'.format(self._zip_code, self._kind)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return 'index'


class ForecastSensor(BaseSensor):
    """Define sensor related to forecast data."""

    async def async_update(self):
        """Update the sensor."""
        await self.pollen.async_update()
        if not self.pollen.data:
            return

        data = self.pollen.data[self._kind].get('Location')
        if not data:
            return

        indices = [p['Index'] for p in data['periods']]
        average = round(mean(indices), 1)
        [rating] = [
            i['label'] for i in RATING_MAPPING
            if i['minimum'] <= average <= i['maximum']
        ]

        self._attrs.update({
            ATTR_CITY: data['City'].title(),
            ATTR_RATING: rating,
            ATTR_STATE: data['State'],
            ATTR_TREND: calculate_trend(indices),
            ATTR_ZIP_CODE: data['ZIP']
        })

        if self._kind == TYPE_ALLERGY_FORECAST:
            outlook = self.pollen.data[TYPE_ALLERGY_OUTLOOK]
            self._attrs[ATTR_OUTLOOK] = outlook['Outlook']
            self._attrs[ATTR_SEASON] = outlook['Season']

        self._state = average


class HistoricalSensor(BaseSensor):
    """Define sensor related to historical data."""

    async def async_update(self):
        """Update the sensor."""
        await self.pollen.async_update()
        if not self.pollen.data:
            return

        data = self.pollen.data[self._kind].get('Location')
        if not data:
            return

        indices = [p['Index'] for p in data['periods']]
        average = round(mean(indices), 1)

        self._attrs.update({
            ATTR_CITY: data['City'].title(),
            ATTR_RATING: calculate_average_rating(indices),
            ATTR_STATE: data['State'],
            ATTR_TREND: calculate_trend(indices),
            ATTR_ZIP_CODE: data['ZIP']
        })

        self._state = average


class IndexSensor(BaseSensor):
    """Define sensor related to indices."""

    async def async_update(self):
        """Update the sensor."""
        await self.pollen.async_update()
        if not self.pollen.data:
            return

        data = {}
        if self._kind in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                          TYPE_ALLERGY_YESTERDAY):
            data = self.pollen.data[TYPE_ALLERGY_INDEX].get('Location')
        elif self._kind in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                            TYPE_ASTHMA_YESTERDAY):
            data = self.pollen.data[TYPE_ASTHMA_INDEX].get('Location')

        if not data:
            return

        key = self._kind.split('_')[-1].title()
        [period] = [p for p in data['periods'] if p['Type'] == key]
        [rating] = [
            i['label'] for i in RATING_MAPPING
            if i['minimum'] <= period['Index'] <= i['maximum']
        ]

        self._attrs.update({
            ATTR_CITY: data['City'].title(),
            ATTR_RATING: rating,
            ATTR_STATE: data['State'],
            ATTR_ZIP_CODE: data['ZIP']
        })

        if self._kind in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                          TYPE_ALLERGY_YESTERDAY):
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
        elif self._kind in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                            TYPE_ASTHMA_YESTERDAY):
            for idx, attrs in enumerate(period['Triggers']):
                index = idx + 1
                self._attrs.update({
                    '{0}_{1}'.format(ATTR_ALLERGEN_NAME, index):
                        attrs['Name'],
                    '{0}_{1}'.format(ATTR_ALLERGEN_AMOUNT, index):
                        attrs['PPM'],
                })

        self._state = period['Index']


class PollenComData:
    """Define a data object to retrieve info from Pollen.com."""

    def __init__(self, client, sensor_types):
        """Initialize."""
        self._client = client
        self._sensor_types = sensor_types
        self.data = {}

    async def _get_data(self, method, key):
        """Return API data from a specific call."""
        from pypollencom.errors import PollenComError

        try:
            data = await method()
            self.data[key] = data
        except PollenComError as err:
            _LOGGER.error('Unable to get "%s" data: %s', key, err)
            self.data[key] = {}

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Update Pollen.com data."""
        from pypollencom.errors import InvalidZipError

        # Pollen.com requires a bit more complicated error handling, given that
        # it sometimes has parts (but not the whole thing) go down:
        #
        # 1. If `InvalidZipError` is thrown, quit everything immediately.
        # 2. If an individual request throws any other error, try the others.

        try:
            if TYPE_ALLERGY_FORECAST in self._sensor_types:
                await self._get_data(
                    self._client.allergens.extended, TYPE_ALLERGY_FORECAST)
                await self._get_data(
                    self._client.allergens.outlook, TYPE_ALLERGY_OUTLOOK)

            if TYPE_ALLERGY_HISTORIC in self._sensor_types:
                await self._get_data(
                    self._client.allergens.historic, TYPE_ALLERGY_HISTORIC)

            if any(s in self._sensor_types
                   for s in [TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                             TYPE_ALLERGY_YESTERDAY]):
                await self._get_data(
                    self._client.allergens.current, TYPE_ALLERGY_INDEX)

            if TYPE_ASTHMA_FORECAST in self._sensor_types:
                await self._get_data(
                    self._client.asthma.extended, TYPE_ASTHMA_FORECAST)

            if TYPE_ASTHMA_HISTORIC in self._sensor_types:
                await self._get_data(
                    self._client.asthma.historic, TYPE_ASTHMA_HISTORIC)

            if any(s in self._sensor_types
                   for s in [TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                             TYPE_ASTHMA_YESTERDAY]):
                await self._get_data(
                    self._client.asthma.current, TYPE_ASTHMA_INDEX)

            if TYPE_DISEASE_FORECAST in self._sensor_types:
                await self._get_data(
                    self._client.disease.extended, TYPE_DISEASE_FORECAST)

            _LOGGER.debug("New data retrieved: %s", self.data)
        except InvalidZipError:
            _LOGGER.error(
                "Cannot retrieve data for ZIP code: %s", self._client.zip_code)
            self.data = {}
