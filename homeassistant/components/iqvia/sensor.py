"""Support for IQVIA sensors."""

from __future__ import annotations

from statistics import mean
from typing import Any, NamedTuple, cast

import numpy as np

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_STATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IQVIAEntity
from .const import (
    DOMAIN,
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
)

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

API_CATEGORY_MAPPING = {
    TYPE_ALLERGY_TODAY: TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_TOMORROW: TYPE_ALLERGY_INDEX,
    TYPE_ASTHMA_TODAY: TYPE_ASTHMA_INDEX,
    TYPE_ASTHMA_TOMORROW: TYPE_ASTHMA_INDEX,
    TYPE_DISEASE_TODAY: TYPE_DISEASE_INDEX,
}


class Rating(NamedTuple):
    """Assign label to value range."""

    label: str
    minimum: float
    maximum: float


RATING_MAPPING: list[Rating] = [
    Rating(label="Low", minimum=0.0, maximum=2.4),
    Rating(label="Low/Medium", minimum=2.5, maximum=4.8),
    Rating(label="Medium", minimum=4.9, maximum=7.2),
    Rating(label="Medium/High", minimum=7.3, maximum=9.6),
    Rating(label="High", minimum=9.7, maximum=12),
]


TREND_FLAT = "Flat"
TREND_INCREASING = "Increasing"
TREND_SUBSIDING = "Subsiding"


FORECAST_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=TYPE_ALLERGY_FORECAST,
        name="Allergy index: forecasted average",
        icon="mdi:flower",
    ),
    SensorEntityDescription(
        key=TYPE_ASTHMA_FORECAST,
        name="Asthma index: forecasted average",
        icon="mdi:flower",
    ),
    SensorEntityDescription(
        key=TYPE_DISEASE_FORECAST,
        name="Cold & flu: forecasted average",
        icon="mdi:snowflake",
    ),
)

INDEX_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=TYPE_ALLERGY_TODAY,
        name="Allergy index: today",
        icon="mdi:flower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_ALLERGY_TOMORROW,
        name="Allergy index: tomorrow",
        icon="mdi:flower",
    ),
    SensorEntityDescription(
        key=TYPE_ASTHMA_TODAY,
        name="Asthma index: today",
        icon="mdi:flower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_ASTHMA_TOMORROW,
        name="Asthma index: tomorrow",
        icon="mdi:flower",
    ),
    SensorEntityDescription(
        key=TYPE_DISEASE_TODAY,
        name="Cold & flu index: today",
        icon="mdi:pill",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up IQVIA sensors based on a config entry."""
    sensors: list[ForecastSensor | IndexSensor] = [
        ForecastSensor(
            hass.data[DOMAIN][entry.entry_id][
                API_CATEGORY_MAPPING.get(description.key, description.key)
            ],
            entry,
            description,
        )
        for description in FORECAST_SENSOR_DESCRIPTIONS
    ]
    sensors.extend(
        [
            IndexSensor(
                hass.data[DOMAIN][entry.entry_id][
                    API_CATEGORY_MAPPING.get(description.key, description.key)
                ],
                entry,
                description,
            )
            for description in INDEX_SENSOR_DESCRIPTIONS
        ]
    )

    async_add_entities(sensors)


@callback
def calculate_trend(indices: list[float]) -> str:
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


class ForecastSensor(IQVIAEntity, SensorEntity):
    """Define sensor related to forecast data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor."""
        if not self.available:
            return

        data = self.coordinator.data.get("Location", {})

        if not data.get("periods"):
            return

        indices = [p["Index"] for p in data["periods"]]
        average = round(mean(indices), 1)
        [rating] = [
            i.label for i in RATING_MAPPING if i.minimum <= average <= i.maximum
        ]

        self._attr_native_value = average
        self._attr_extra_state_attributes.update(
            {
                ATTR_CITY: data["City"].title(),
                ATTR_RATING: rating,
                ATTR_STATE: data["State"],
                ATTR_TREND: calculate_trend(indices),
                ATTR_ZIP_CODE: data["ZIP"],
            }
        )

        if self.entity_description.key == TYPE_ALLERGY_FORECAST:
            outlook_coordinator = self.hass.data[DOMAIN][self._entry.entry_id][
                TYPE_ALLERGY_OUTLOOK
            ]

            if not outlook_coordinator.last_update_success:
                return

            self._attr_extra_state_attributes[ATTR_OUTLOOK] = (
                outlook_coordinator.data.get("Outlook")
            )
            self._attr_extra_state_attributes[ATTR_SEASON] = (
                outlook_coordinator.data.get("Season")
            )


class IndexSensor(IQVIAEntity, SensorEntity):
    """Define sensor related to indices."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor."""
        if not self.coordinator.last_update_success:
            return

        try:
            if self.entity_description.key in (
                TYPE_ALLERGY_TODAY,
                TYPE_ALLERGY_TOMORROW,
                TYPE_ASTHMA_TODAY,
                TYPE_ASTHMA_TOMORROW,
                TYPE_DISEASE_TODAY,
            ):
                data = self.coordinator.data.get("Location")
        except KeyError:
            return

        key = self.entity_description.key.split("_")[-1].title()

        try:
            period = next(p for p in data["periods"] if p["Type"] == key)  # type: ignore[index]
        except StopIteration:
            return

        data = cast(dict[str, Any], data)
        [rating] = [
            i.label for i in RATING_MAPPING if i.minimum <= period["Index"] <= i.maximum
        ]

        self._attr_extra_state_attributes.update(
            {
                ATTR_CITY: data["City"].title(),
                ATTR_RATING: rating,
                ATTR_STATE: data["State"],
                ATTR_ZIP_CODE: data["ZIP"],
            }
        )

        if self.entity_description.key in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW):
            for idx, attrs in enumerate(period["Triggers"]):
                index = idx + 1
                self._attr_extra_state_attributes.update(
                    {
                        f"{ATTR_ALLERGEN_GENUS}_{index}": attrs["Genus"],
                        f"{ATTR_ALLERGEN_NAME}_{index}": attrs["Name"],
                        f"{ATTR_ALLERGEN_TYPE}_{index}": attrs["PlantType"],
                    }
                )
        elif self.entity_description.key in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW):
            for idx, attrs in enumerate(period["Triggers"]):
                index = idx + 1
                self._attr_extra_state_attributes.update(
                    {
                        f"{ATTR_ALLERGEN_NAME}_{index}": attrs["Name"],
                        f"{ATTR_ALLERGEN_AMOUNT}_{index}": attrs["PPM"],
                    }
                )
        elif self.entity_description.key == TYPE_DISEASE_TODAY:
            for attrs in period["Triggers"]:
                self._attr_extra_state_attributes[f"{attrs['Name'].lower()}_index"] = (
                    attrs["Index"]
                )

        self._attr_native_value = period["Index"]
