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
    ATTR_ATTRIBUTION, ATTR_STATE, CONF_MONITORED_CONDITIONS
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, slugify

REQUIREMENTS = ['pypollencom==1.1.2']
_LOGGER = logging.getLogger(__name__)

ATTR_ALLERGEN_GENUS = 'primary_allergen_genus'
ATTR_ALLERGEN_NAME = 'primary_allergen_name'
ATTR_ALLERGEN_TYPE = 'primary_allergen_type'
ATTR_CITY = 'city'
ATTR_OUTLOOK = 'outlook'
ATTR_RATING = 'rating'
ATTR_SEASON = 'season'
ATTR_TREND = 'trend'
ATTR_ZIP_CODE = 'zip_code'

CONF_ZIP_CODE = 'zip_code'

DEFAULT_ATTRIBUTION = 'Data provided by IQVIA™'

MIN_TIME_UPDATE_AVERAGES = timedelta(hours=12)
MIN_TIME_UPDATE_INDICES = timedelta(minutes=10)

CONDITIONS = {
    'allergy_average_forecasted': (
        'Allergy Index: Forecasted Average',
        'AllergyAverageSensor',
        'allergy_average_data',
        {'data_attr': 'extended_data'},
        'mdi:flower'
    ),
    'allergy_average_historical': (
        'Allergy Index: Historical Average',
        'AllergyAverageSensor',
        'allergy_average_data',
        {'data_attr': 'historic_data'},
        'mdi:flower'
    ),
    'allergy_index_today': (
        'Allergy Index: Today',
        'AllergyIndexSensor',
        'allergy_index_data',
        {'key': 'Today'},
        'mdi:flower'
    ),
    'allergy_index_tomorrow': (
        'Allergy Index: Tomorrow',
        'AllergyIndexSensor',
        'allergy_index_data',
        {'key': 'Tomorrow'},
        'mdi:flower'
    ),
    'allergy_index_yesterday': (
        'Allergy Index: Yesterday',
        'AllergyIndexSensor',
        'allergy_index_data',
        {'key': 'Yesterday'},
        'mdi:flower'
    ),
    'disease_average_forecasted': (
        'Cold & Flu: Forecasted Average',
        'AllergyAverageSensor',
        'disease_average_data',
        {'data_attr': 'extended_data'},
        'mdi:snowflake'
    )
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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIP_CODE): str,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(CONDITIONS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pypollencom import Client

    _LOGGER.debug('Configuration data: %s', config)

    client = Client(config[CONF_ZIP_CODE])
    datas = {
        'allergy_average_data': AllergyAveragesData(client),
        'allergy_index_data': AllergyIndexData(client),
        'disease_average_data': DiseaseData(client)
    }
    classes = {
        'AllergyAverageSensor': AllergyAverageSensor,
        'AllergyIndexSensor': AllergyIndexSensor
    }

    for data in datas.values():
        data.update()

    sensors = []
    for condition in config[CONF_MONITORED_CONDITIONS]:
        name, sensor_class, data_key, params, icon = CONDITIONS[condition]
        sensors.append(classes[sensor_class](
            datas[data_key],
            params,
            name,
            icon,
            config[CONF_ZIP_CODE]
        ))

    add_devices(sensors, True)


def calculate_trend(list_of_nums):
    """Calculate the most common rating as a trend."""
    ratings = list(
        r['label'] for n in list_of_nums
        for r in RATING_MAPPING
        if r['minimum'] <= n <= r['maximum'])
    return max(set(ratings), key=ratings.count)


class BaseSensor(Entity):
    """Define a base class for all of our sensors."""

    def __init__(self, data, data_params, name, icon, unique_id):
        """Initialize the sensor."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._name = name
        self._data_params = data_params
        self._state = None
        self._unit = None
        self._unique_id = unique_id
        self.data = data

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
        return '{0}_{1}'.format(self._unique_id, slugify(self._name))

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit


class AllergyAverageSensor(BaseSensor):
    """Define a sensor to show allergy average information."""

    def update(self):
        """Update the status of the sensor."""
        self.data.update()

        try:
            data_attr = getattr(self.data, self._data_params['data_attr'])
            indices = [p['Index'] for p in data_attr['Location']['periods']]
            self._attrs[ATTR_TREND] = calculate_trend(indices)
        except KeyError:
            _LOGGER.error("Pollen.com API didn't return any data")
            return

        try:
            self._attrs[ATTR_CITY] = data_attr['Location']['City'].title()
            self._attrs[ATTR_STATE] = data_attr['Location']['State']
            self._attrs[ATTR_ZIP_CODE] = data_attr['Location']['ZIP']
        except KeyError:
            _LOGGER.debug('Location data not included in API response')
            self._attrs[ATTR_CITY] = None
            self._attrs[ATTR_STATE] = None
            self._attrs[ATTR_ZIP_CODE] = None

        average = round(mean(indices), 1)
        [rating] = [
            i['label'] for i in RATING_MAPPING
            if i['minimum'] <= average <= i['maximum']
        ]
        self._attrs[ATTR_RATING] = rating

        self._state = average
        self._unit = 'index'


class AllergyIndexSensor(BaseSensor):
    """Define a sensor to show allergy index information."""

    def update(self):
        """Update the status of the sensor."""
        self.data.update()

        try:
            location_data = self.data.current_data['Location']
            [period] = [
                p for p in location_data['periods']
                if p['Type'] == self._data_params['key']
            ]
            [rating] = [
                i['label'] for i in RATING_MAPPING
                if i['minimum'] <= period['Index'] <= i['maximum']
            ]

            for i in range(3):
                index = i + 1
                try:
                    data = period['Triggers'][i]
                    self._attrs['{0}_{1}'.format(
                        ATTR_ALLERGEN_GENUS, index)] = data['Genus']
                    self._attrs['{0}_{1}'.format(
                        ATTR_ALLERGEN_NAME, index)] = data['Name']
                    self._attrs['{0}_{1}'.format(
                        ATTR_ALLERGEN_TYPE, index)] = data['PlantType']
                except IndexError:
                    self._attrs['{0}_{1}'.format(
                        ATTR_ALLERGEN_GENUS, index)] = None
                    self._attrs['{0}_{1}'.format(
                        ATTR_ALLERGEN_NAME, index)] = None
                    self._attrs['{0}_{1}'.format(
                        ATTR_ALLERGEN_TYPE, index)] = None

            self._attrs[ATTR_RATING] = rating

        except KeyError:
            _LOGGER.error("Pollen.com API didn't return any data")
            return

        try:
            self._attrs[ATTR_CITY] = location_data['City'].title()
            self._attrs[ATTR_STATE] = location_data['State']
            self._attrs[ATTR_ZIP_CODE] = location_data['ZIP']
        except KeyError:
            _LOGGER.debug('Location data not included in API response')
            self._attrs[ATTR_CITY] = None
            self._attrs[ATTR_STATE] = None
            self._attrs[ATTR_ZIP_CODE] = None

        try:
            self._attrs[ATTR_OUTLOOK] = self.data.outlook_data['Outlook']
        except KeyError:
            _LOGGER.debug('Outlook data not included in API response')
            self._attrs[ATTR_OUTLOOK] = None

        try:
            self._attrs[ATTR_SEASON] = self.data.outlook_data['Season']
        except KeyError:
            _LOGGER.debug('Season data not included in API response')
            self._attrs[ATTR_SEASON] = None

        try:
            self._attrs[ATTR_TREND] = self.data.outlook_data['Trend'].title()
        except KeyError:
            _LOGGER.debug('Trend data not included in API response')
            self._attrs[ATTR_TREND] = None

        self._state = period['Index']
        self._unit = 'index'


class DataBase(object):
    """Define a generic data object."""

    def __init__(self, client):
        """Initialize."""
        self._client = client

    def _get_client_data(self, module, operation):
        """Get data from a particular point in the API."""
        from pypollencom.exceptions import HTTPError

        data = {}
        try:
            data = getattr(getattr(self._client, module), operation)()
            _LOGGER.debug('Received "%s_%s" data: %s', module, operation, data)
        except HTTPError as exc:
            _LOGGER.error('An error occurred while retrieving data')
            _LOGGER.debug(exc)

        return data


class AllergyAveragesData(DataBase):
    """Define an object to averages on future and historical allergy data."""

    def __init__(self, client):
        """Initialize."""
        super().__init__(client)
        self.extended_data = None
        self.historic_data = None

    @Throttle(MIN_TIME_UPDATE_AVERAGES)
    def update(self):
        """Update with new data."""
        self.extended_data = self._get_client_data('allergens', 'extended')
        self.historic_data = self._get_client_data('allergens', 'historic')


class AllergyIndexData(DataBase):
    """Define an object to retrieve current allergy index info."""

    def __init__(self, client):
        """Initialize."""
        super().__init__(client)
        self.current_data = None
        self.outlook_data = None

    @Throttle(MIN_TIME_UPDATE_INDICES)
    def update(self):
        """Update with new index data."""
        self.current_data = self._get_client_data('allergens', 'current')
        self.outlook_data = self._get_client_data('allergens', 'outlook')


class DiseaseData(DataBase):
    """Define an object to retrieve current disease index info."""

    def __init__(self, client):
        """Initialize."""
        super().__init__(client)
        self.extended_data = None

    @Throttle(MIN_TIME_UPDATE_INDICES)
    def update(self):
        """Update with new cold/flu data."""
        self.extended_data = self._get_client_data('disease', 'extended')
