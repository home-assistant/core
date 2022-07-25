"""Support for user- and CDC-based flu info sensors from Flu Near You."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Union, cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_STATE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CATEGORY_CDC_REPORT, CATEGORY_USER_REPORT, DOMAIN

ATTR_CITY = "city"
ATTR_REPORTED_DATE = "reported_date"
ATTR_REPORTED_LATITUDE = "reported_latitude"
ATTR_REPORTED_LONGITUDE = "reported_longitude"
ATTR_STATE_REPORTS_LAST_WEEK = "state_reports_last_week"
ATTR_STATE_REPORTS_THIS_WEEK = "state_reports_this_week"
ATTR_ZIP_CODE = "zip_code"

SENSOR_TYPE_CDC_LEVEL = "level"
SENSOR_TYPE_CDC_LEVEL2 = "level2"
SENSOR_TYPE_USER_CHICK = "chick"
SENSOR_TYPE_USER_DENGUE = "dengue"
SENSOR_TYPE_USER_FLU = "flu"
SENSOR_TYPE_USER_LEPTO = "lepto"
SENSOR_TYPE_USER_NO_SYMPTOMS = "none"
SENSOR_TYPE_USER_SYMPTOMS = "symptoms"
SENSOR_TYPE_USER_TOTAL = "total"

CDC_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CDC_LEVEL,
        name="CDC level",
        icon="mdi:biohazard",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_CDC_LEVEL2,
        name="CDC level 2",
        icon="mdi:biohazard",
    ),
)

USER_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_CHICK,
        name="Avian flu symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_DENGUE,
        name="Dengue fever symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_FLU,
        name="Flu symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_LEPTO,
        name="Leptospirosis symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_NO_SYMPTOMS,
        name="No symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_SYMPTOMS,
        name="Flu-like symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_TOTAL,
        name="Total symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

EXTENDED_SENSOR_TYPE_MAPPING = {
    SENSOR_TYPE_USER_FLU: "ili",
    SENSOR_TYPE_USER_NO_SYMPTOMS: "no_symptoms",
    SENSOR_TYPE_USER_TOTAL: "total_surveys",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Flu Near You sensors based on a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    sensors: list[CdcSensor | UserSensor] = [
        CdcSensor(coordinators[CATEGORY_CDC_REPORT], entry, description)
        for description in CDC_SENSOR_DESCRIPTIONS
    ]
    sensors.extend(
        [
            UserSensor(coordinators[CATEGORY_USER_REPORT], entry, description)
            for description in USER_SENSOR_DESCRIPTIONS
        ]
    )
    async_add_entities(sensors)


class FluNearYouSensor(CoordinatorEntity, SensorEntity):
    """Define a base Flu Near You sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{entry.data[CONF_LATITUDE]},"
            f"{entry.data[CONF_LONGITUDE]}_{description.key}"
        )
        self._entry = entry
        self.entity_description = description


class CdcSensor(FluNearYouSensor):
    """Define a sensor for CDC reports."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return {
            ATTR_REPORTED_DATE: self.coordinator.data["week_date"],
            ATTR_STATE: self.coordinator.data["name"],
        }

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return cast(
            Union[str, None], self.coordinator.data[self.entity_description.key]
        )


class UserSensor(FluNearYouSensor):
    """Define a sensor for user reports."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {
            ATTR_CITY: self.coordinator.data["local"]["city"].split("(")[0],
            ATTR_REPORTED_LATITUDE: self.coordinator.data["local"]["latitude"],
            ATTR_REPORTED_LONGITUDE: self.coordinator.data["local"]["longitude"],
            ATTR_STATE: self.coordinator.data["state"]["name"],
            ATTR_ZIP_CODE: self.coordinator.data["local"]["zip"],
        }

        if self.entity_description.key in self.coordinator.data["state"]["data"]:
            states_key = self.entity_description.key
        elif self.entity_description.key in EXTENDED_SENSOR_TYPE_MAPPING:
            states_key = EXTENDED_SENSOR_TYPE_MAPPING[self.entity_description.key]

        attrs[ATTR_STATE_REPORTS_THIS_WEEK] = self.coordinator.data["state"]["data"][
            states_key
        ]
        attrs[ATTR_STATE_REPORTS_LAST_WEEK] = self.coordinator.data["state"][
            "last_week_data"
        ][states_key]

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        if self.entity_description.key == SENSOR_TYPE_USER_TOTAL:
            value = sum(
                v
                for k, v in self.coordinator.data["local"].items()
                if k
                in (
                    SENSOR_TYPE_USER_CHICK,
                    SENSOR_TYPE_USER_DENGUE,
                    SENSOR_TYPE_USER_FLU,
                    SENSOR_TYPE_USER_LEPTO,
                    SENSOR_TYPE_USER_SYMPTOMS,
                )
            )
        else:
            value = self.coordinator.data["local"][self.entity_description.key]

        return cast(int, value)
