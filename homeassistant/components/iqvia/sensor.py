"""Support for IQVIA sensors."""
import logging
from statistics import mean

import numpy as np

from homeassistant.components.iqvia import (
    DATA_CLIENT,
    DOMAIN,
    SENSORS,
    TYPE_ALLERGY_FORECAST,
    TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_OUTLOOK,
    TYPE_ALLERGY_TODAY,
    TYPE_ALLERGY_TOMORROW,
    TYPE_ASTHMA_FORECAST,
    TYPE_ASTHMA_INDEX,
    TYPE_ASTHMA_TODAY,
    TYPE_ASTHMA_TOMORROW,
    TYPE_DISEASE_FORECAST,
    TYPE_DISEASE_INDEX,
    TYPE_DISEASE_TODAY,
    IQVIAEntity,
)
from homeassistant.const import ATTR_STATE

_LOGGER = logging.getLogger(__name__)

ATTR_ALLERGEN_AMOUNT = "allergen_amount"
ATTR_ALLERGEN_GENUS = "allergen_genus"
ATTR_ALLERGEN_NAME = "allergen_name"
ATTR_ALLERGEN_TYPE = "allergen_type"
ATTR_CITY = "city"
ATTR_OUTLOOK = "outlook"
ATTR_RATING = "rating"
ATTR_SEASON = "season"
ATTR_TREND = "trend"
ATTR_ZIP_CODE = "zip_code"

RATING_MAPPING = [
    {"label": "Low", "minimum": 0.0, "maximum": 2.4},
    {"label": "Low/Medium", "minimum": 2.5, "maximum": 4.8},
    {"label": "Medium", "minimum": 4.9, "maximum": 7.2},
    {"label": "Medium/High", "minimum": 7.3, "maximum": 9.6},
    {"label": "High", "minimum": 9.7, "maximum": 12},
]

TREND_FLAT = "Flat"
TREND_INCREASING = "Increasing"
TREND_SUBSIDING = "Subsiding"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up IQVIA sensors based on a config entry."""
    iqvia = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_class_mapping = {
        TYPE_ALLERGY_FORECAST: ForecastSensor,
        TYPE_ALLERGY_TODAY: IndexSensor,
        TYPE_ALLERGY_TOMORROW: IndexSensor,
        TYPE_ASTHMA_FORECAST: ForecastSensor,
        TYPE_ASTHMA_TODAY: IndexSensor,
        TYPE_ASTHMA_TOMORROW: IndexSensor,
        TYPE_DISEASE_FORECAST: ForecastSensor,
        TYPE_DISEASE_TODAY: IndexSensor,
    }

    sensors = []
    for sensor_type in iqvia.sensor_types:
        klass = sensor_class_mapping[sensor_type]
        name, icon = SENSORS[sensor_type]
        sensors.append(klass(iqvia, sensor_type, name, icon, iqvia.zip_code))

    async_add_entities(sensors, True)


def calculate_trend(indices):
    """Calculate the "moving average" of a set of indices."""
    index_range = np.arange(0, len(indices))
    index_array = np.array(indices)
    linear_fit = np.polyfit(index_range, index_array, 1)
    slope = round(linear_fit[0], 2)

    if slope > 0:
        return TREND_INCREASING

    if slope < 0:
        return TREND_SUBSIDING

    return TREND_FLAT


class ForecastSensor(IQVIAEntity):
    """Define sensor related to forecast data."""

    async def async_update(self):
        """Update the sensor."""
        if not self._iqvia.data:
            return

        data = self._iqvia.data[self._type].get("Location")
        if not data or not data.get("periods"):
            return

        indices = [p["Index"] for p in data["periods"]]
        average = round(mean(indices), 1)
        [rating] = [
            i["label"]
            for i in RATING_MAPPING
            if i["minimum"] <= average <= i["maximum"]
        ]

        self._attrs.update(
            {
                ATTR_CITY: data["City"].title(),
                ATTR_RATING: rating,
                ATTR_STATE: data["State"],
                ATTR_TREND: calculate_trend(indices),
                ATTR_ZIP_CODE: data["ZIP"],
            }
        )

        if self._type == TYPE_ALLERGY_FORECAST:
            outlook = self._iqvia.data[TYPE_ALLERGY_OUTLOOK]
            self._attrs[ATTR_OUTLOOK] = outlook.get("Outlook")
            self._attrs[ATTR_SEASON] = outlook.get("Season")

        self._state = average


class IndexSensor(IQVIAEntity):
    """Define sensor related to indices."""

    async def async_update(self):
        """Update the sensor."""
        if not self._iqvia.data:
            return

        data = {}
        if self._type in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW):
            data = self._iqvia.data[TYPE_ALLERGY_INDEX].get("Location")
        elif self._type in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW):
            data = self._iqvia.data[TYPE_ASTHMA_INDEX].get("Location")
        elif self._type == TYPE_DISEASE_TODAY:
            data = self._iqvia.data[TYPE_DISEASE_INDEX].get("Location")

        if not data:
            return

        key = self._type.split("_")[-1].title()
        [period] = [p for p in data["periods"] if p["Type"] == key]
        [rating] = [
            i["label"]
            for i in RATING_MAPPING
            if i["minimum"] <= period["Index"] <= i["maximum"]
        ]

        self._attrs.update(
            {
                ATTR_CITY: data["City"].title(),
                ATTR_RATING: rating,
                ATTR_STATE: data["State"],
                ATTR_ZIP_CODE: data["ZIP"],
            }
        )

        if self._type in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW):
            for idx, attrs in enumerate(period["Triggers"]):
                index = idx + 1
                self._attrs.update(
                    {
                        f"{ATTR_ALLERGEN_GENUS}_{index}": attrs["Genus"],
                        f"{ATTR_ALLERGEN_NAME}_{index}": attrs["Name"],
                        f"{ATTR_ALLERGEN_TYPE}_{index}": attrs["PlantType"],
                    }
                )
        elif self._type in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW):
            for idx, attrs in enumerate(period["Triggers"]):
                index = idx + 1
                self._attrs.update(
                    {
                        f"{ATTR_ALLERGEN_NAME}_{index}": attrs["Name"],
                        f"{ATTR_ALLERGEN_AMOUNT}_{index}": attrs["PPM"],
                    }
                )
        elif self._type == TYPE_DISEASE_TODAY:
            for attrs in period["Triggers"]:
                self._attrs["{0}_index".format(attrs["Name"].lower())] = attrs["Index"]

        self._state = period["Index"]
