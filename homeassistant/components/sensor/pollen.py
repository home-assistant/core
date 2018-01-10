"""
Support for Pollen.com allergen and disease sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pollen/
"""
from logging import getLogger
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_STATE, CONF_MONITORED_CONDITIONS
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pypollencom==1.1.1']
_LOGGER = getLogger(__name__)

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
    vol.Required(CONF_ZIP_CODE): cv.positive_int,
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

    for data in datas.values():
        data.update()

    sensors = []
    for condition in config.get(CONF_MONITORED_CONDITIONS, []):
        name, sensor_class, data_key, params, icon = CONDITIONS[condition]
        sensors.append(globals()[sensor_class](
            datas[data_key],
            params,
            name,
            icon
        ))

    add_devices(sensors, True)


def average_of_list(list_of_nums, decimal_places=1):
    """Returns the average of a list of ints."""
    return round(sum(list_of_nums, 0.0)/len(list_of_nums), decimal_places)


def calculate_trend(list_of_nums):
    """Returns the average of a list of ints."""
    ratings = list(
        map(
            (lambda n: [
                r['label'] for r in RATING_MAPPING
                if r['minimum'] <= n <= r['maximum']
            ][0]),
            list_of_nums
        )
    )
    return max(set(ratings), key=ratings.count)


def merge_two_dicts(dict1, dict2):
    """Merge two dicts into a new dict as a shallow copy."""
    final = dict1.copy()
    final.update(dict2)
    return final


class BaseSensor(Entity):
    """Define a base class for all of our sensors."""

    def __init__(self, data, data_params, name, icon):
        """Initialize the sensor."""
        self._attrs = {}
        self._icon = icon
        self._name = name
        self._data_params = data_params
        self._state = None
        self._unit = None
        self.data = data

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return merge_two_dicts(
            self._attrs, {
                ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION
            }
        )

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
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit


class AllergyAverageSensor(BaseSensor):
    """Define a sensor to show allergy average information."""

    def update(self):
        """Update the status of the sensor."""
        self.data.update()

        data_attr = getattr(self.data, self._data_params['data_attr'])
        indices = [
            p['Index']
            for p in data_attr['Location']['periods']
        ]
        average = average_of_list(indices)

        self._attrs[ATTR_CITY] = data_attr['Location']['City'].title()
        self._attrs[ATTR_STATE] = data_attr['Location']['State']
        self._attrs[ATTR_TREND] = calculate_trend(indices)
        self._attrs[ATTR_ZIP_CODE] = data_attr['Location']['ZIP']

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

        location_data = self.data.current_data['Location']
        [period] = [
            p for p in location_data['periods']
            if p['Type'] == self._data_params['key']
        ]

        self._attrs[ATTR_CITY] = location_data['City'].title()
        self._attrs[ATTR_ALLERGEN_GENUS] = period['Triggers'][0]['Genus']
        self._attrs[ATTR_ALLERGEN_NAME] = period['Triggers'][0]['Name']
        self._attrs[ATTR_ALLERGEN_TYPE] = period['Triggers'][0]['PlantType']
        self._attrs[ATTR_OUTLOOK] = self.data.outlook_data['Outlook']
        self._attrs[ATTR_SEASON] = self.data.outlook_data['Season']
        self._attrs[ATTR_TREND] = self.data.outlook_data[
            'Trend'].title()
        self._attrs[ATTR_STATE] = location_data['State']
        self._attrs[ATTR_ZIP_CODE] = location_data['ZIP']

        [rating] = [
            i['label'] for i in RATING_MAPPING
            if i['minimum'] <= period['Index'] <= i['maximum']
        ]
        self._attrs[ATTR_RATING] = rating

        self._state = period['Index']
        self._unit = 'index'


class AllergyAveragesData(object):
    """Define an object to averages on future and historical allergy data."""

    def __init__(self, client):
        """Initialize."""
        self._client = client
        self.extended_data = None
        self.historic_data = None

    @Throttle(MIN_TIME_UPDATE_AVERAGES)
    def update(self):
        """Update with new data."""
        from pypollencom.exceptions import HTTPError

        try:
            self.extended_data = self._client.allergens.extended()
            _LOGGER.debug('Received "extended" allergy data: %s',
                          self.extended_data)

            self.historic_data = self._client.allergens.historic()
            _LOGGER.debug('Received "historic" allergy data: %s',
                          self.historic_data)
        except HTTPError as exc:
            _LOGGER.error('An error occurred while retrieving allergen data')
            _LOGGER.debug(exc)


class AllergyIndexData(object):
    """Define an object to retrieve current allergy index info."""

    def __init__(self, client):
        """Initialize."""
        self._client = client
        self.current_data = None
        self.outlook_data = None

    @Throttle(MIN_TIME_UPDATE_INDICES)
    def update(self):
        """Update with new AirVisual data."""
        from pypollencom.exceptions import HTTPError

        try:
            self.current_data = self._client.allergens.current()
            _LOGGER.debug('Received "current" allergy data: %s',
                          self.current_data)

            self.outlook_data = self._client.allergens.outlook()
            _LOGGER.debug('Received "outlook" allergy data: %s',
                          self.outlook_data)
        except HTTPError as exc:
            _LOGGER.error('An error occurred while retrieving allergen data')
            _LOGGER.debug(exc)


class DiseaseData(object):
    """Define an object to retrieve current disease index info."""

    def __init__(self, client):
        """Initialize."""
        self._client = client
        self.extended_data = None

    @Throttle(MIN_TIME_UPDATE_INDICES)
    def update(self):
        """Update with new AirVisual data."""
        from pypollencom.exceptions import HTTPError

        try:
            self.extended_data = self._client.disease.extended()
            _LOGGER.debug('Received "extended" disease data: %s',
                          self.extended_data)
        except HTTPError as exc:
            _LOGGER.error('An error occurred while retrieving disease data')
            _LOGGER.debug(exc)
