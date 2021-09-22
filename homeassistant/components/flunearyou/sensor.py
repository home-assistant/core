"""Support for user- and CDC-based flu info sensors from Flu Near You."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_STATE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CATEGORY_CDC_REPORT, CATEGORY_USER_REPORT, DATA_COORDINATOR, DOMAIN

ATTR_CITY = "city"
ATTR_REPORTED_DATE = "reported_date"
ATTR_REPORTED_LATITUDE = "reported_latitude"
ATTR_REPORTED_LONGITUDE = "reported_longitude"
ATTR_STATE_REPORTS_LAST_WEEK = "state_reports_last_week"
ATTR_STATE_REPORTS_THIS_WEEK = "state_reports_this_week"
ATTR_ZIP_CODE = "zip_code"

DEFAULT_ATTRIBUTION = "Data provided by Flu Near You"

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
        name="CDC Level",
        icon="mdi:biohazard",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_CDC_LEVEL2,
        name="CDC Level 2",
        icon="mdi:biohazard",
    ),
)

USER_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_CHICK,
        name="Avian Flu Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_DENGUE,
        name="Dengue Fever Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_FLU,
        name="Flu Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_LEPTO,
        name="Leptospirosis Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_NO_SYMPTOMS,
        name="No Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_SYMPTOMS,
        name="Flu-like Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_USER_TOTAL,
        name="Total Symptoms",
        icon="mdi:alert",
        native_unit_of_measurement="reports",
        state_class=STATE_CLASS_MEASUREMENT,
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
    coordinators = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._attr_unique_id = (
            f"{entry.data[CONF_LATITUDE]},"
            f"{entry.data[CONF_LONGITUDE]}_{description.key}"
        )
        self._entry = entry
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor."""
        raise NotImplementedError


class CdcSensor(FluNearYouSensor):
    """Define a sensor for CDC reports."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor."""
        self._attr_extra_state_attributes.update(
            {
                ATTR_REPORTED_DATE: self.coordinator.data["week_date"],
                ATTR_STATE: self.coordinator.data["name"],
            }
        )
        self._attr_native_value = self.coordinator.data[self.entity_description.key]


class UserSensor(FluNearYouSensor):
    """Define a sensor for user reports."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor."""
        self._attr_extra_state_attributes.update(
            {
                ATTR_CITY: self.coordinator.data["local"]["city"].split("(")[0],
                ATTR_REPORTED_LATITUDE: self.coordinator.data["local"]["latitude"],
                ATTR_REPORTED_LONGITUDE: self.coordinator.data["local"]["longitude"],
                ATTR_STATE: self.coordinator.data["state"]["name"],
                ATTR_ZIP_CODE: self.coordinator.data["local"]["zip"],
            }
        )

        if self.entity_description.key in self.coordinator.data["state"]["data"]:
            states_key = self.entity_description.key
        elif self.entity_description.key in EXTENDED_SENSOR_TYPE_MAPPING:
            states_key = EXTENDED_SENSOR_TYPE_MAPPING[self.entity_description.key]

        self._attr_extra_state_attributes[
            ATTR_STATE_REPORTS_THIS_WEEK
        ] = self.coordinator.data["state"]["data"][states_key]
        self._attr_extra_state_attributes[
            ATTR_STATE_REPORTS_LAST_WEEK
        ] = self.coordinator.data["state"]["last_week_data"][states_key]

        if self.entity_description.key == SENSOR_TYPE_USER_TOTAL:
            self._attr_native_value = sum(
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
            self._attr_native_value = self.coordinator.data["local"][
                self.entity_description.key
            ]
