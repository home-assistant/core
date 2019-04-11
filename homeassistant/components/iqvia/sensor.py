"""Support for IQVIA sensors."""
import logging
from statistics import mean

from homeassistant.components.iqvia import (
    DATA_CLIENT, DOMAIN, SENSORS, TYPE_ALLERGY_FORECAST, TYPE_ALLERGY_OUTLOOK,
    TYPE_ALLERGY_INDEX, TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
    TYPE_ALLERGY_YESTERDAY, TYPE_ASTHMA_INDEX, TYPE_ASTHMA_TODAY,
    TYPE_ASTHMA_TOMORROW, TYPE_ASTHMA_YESTERDAY, IQVIAEntity)
from homeassistant.const import ATTR_STATE

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


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Configure the platform and add the sensors."""
    iqvia = hass.data[DOMAIN][DATA_CLIENT]

    sensors = []
    for kind in iqvia.sensor_types:
        sensor_class, name, icon = SENSORS[kind]
        sensors.append(
            globals()[sensor_class](iqvia, kind, name, icon, iqvia.zip_code))

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


class ForecastSensor(IQVIAEntity):
    """Define sensor related to forecast data."""

    async def async_update(self):
        """Update the sensor."""
        await self._iqvia.async_update()
        if not self._iqvia.data:
            return

        data = self._iqvia.data[self._kind].get('Location')
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
            outlook = self._iqvia.data[TYPE_ALLERGY_OUTLOOK]
            self._attrs[ATTR_OUTLOOK] = outlook.get('Outlook')
            self._attrs[ATTR_SEASON] = outlook.get('Season')

        self._state = average


class HistoricalSensor(IQVIAEntity):
    """Define sensor related to historical data."""

    async def async_update(self):
        """Update the sensor."""
        await self._iqvia.async_update()
        if not self._iqvia.data:
            return

        data = self._iqvia.data[self._kind].get('Location')
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


class IndexSensor(IQVIAEntity):
    """Define sensor related to indices."""

    async def async_update(self):
        """Update the sensor."""
        await self._iqvia.async_update()
        if not self._iqvia.data:
            return

        data = {}
        if self._kind in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                          TYPE_ALLERGY_YESTERDAY):
            data = self._iqvia.data[TYPE_ALLERGY_INDEX].get('Location')
        elif self._kind in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                            TYPE_ASTHMA_YESTERDAY):
            data = self._iqvia.data[TYPE_ASTHMA_INDEX].get('Location')

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
