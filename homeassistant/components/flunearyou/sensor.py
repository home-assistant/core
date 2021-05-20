"""Support for user- and CDC-based flu info sensors from Flu Near You."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_STATE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

CDC_SENSORS = [
    (SENSOR_TYPE_CDC_LEVEL, "CDC Level", "mdi:biohazard", None),
    (SENSOR_TYPE_CDC_LEVEL2, "CDC Level 2", "mdi:biohazard", None),
]

USER_SENSORS = [
    (SENSOR_TYPE_USER_CHICK, "Avian Flu Symptoms", "mdi:alert", "reports"),
    (SENSOR_TYPE_USER_DENGUE, "Dengue Fever Symptoms", "mdi:alert", "reports"),
    (SENSOR_TYPE_USER_FLU, "Flu Symptoms", "mdi:alert", "reports"),
    (SENSOR_TYPE_USER_LEPTO, "Leptospirosis Symptoms", "mdi:alert", "reports"),
    (SENSOR_TYPE_USER_NO_SYMPTOMS, "No Symptoms", "mdi:alert", "reports"),
    (SENSOR_TYPE_USER_SYMPTOMS, "Flu-like Symptoms", "mdi:alert", "reports"),
    (SENSOR_TYPE_USER_TOTAL, "Total Symptoms", "mdi:alert", "reports"),
]

EXTENDED_SENSOR_TYPE_MAPPING = {
    SENSOR_TYPE_USER_FLU: "ili",
    SENSOR_TYPE_USER_NO_SYMPTOMS: "no_symptoms",
    SENSOR_TYPE_USER_TOTAL: "total_surveys",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Flu Near You sensors based on a config entry."""
    coordinators = hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id]

    sensors = []

    for (sensor_type, name, icon, unit) in CDC_SENSORS:
        sensors.append(
            CdcSensor(
                coordinators[CATEGORY_CDC_REPORT],
                config_entry,
                sensor_type,
                name,
                icon,
                unit,
            )
        )

    for (sensor_type, name, icon, unit) in USER_SENSORS:
        sensors.append(
            UserSensor(
                coordinators[CATEGORY_USER_REPORT],
                config_entry,
                sensor_type,
                name,
                icon,
                unit,
            )
        )

    async_add_entities(sensors)


class FluNearYouSensor(CoordinatorEntity, SensorEntity):
    """Define a base Flu Near You sensor."""

    def __init__(self, coordinator, config_entry, sensor_type, name, icon, unit):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._config_entry = config_entry
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

    @property
    def extra_state_attributes(self):
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
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return (
            f"{self._config_entry.data[CONF_LATITUDE]},"
            f"{self._config_entry.data[CONF_LONGITUDE]}_{self._sensor_type}"
        )

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self):
        """Update the sensor."""
        raise NotImplementedError


class CdcSensor(FluNearYouSensor):
    """Define a sensor for CDC reports."""

    @callback
    def update_from_latest_data(self):
        """Update the sensor."""
        self._attrs.update(
            {
                ATTR_REPORTED_DATE: self.coordinator.data["week_date"],
                ATTR_STATE: self.coordinator.data["name"],
            }
        )
        self._state = self.coordinator.data[self._sensor_type]


class UserSensor(FluNearYouSensor):
    """Define a sensor for user reports."""

    @callback
    def update_from_latest_data(self):
        """Update the sensor."""
        self._attrs.update(
            {
                ATTR_CITY: self.coordinator.data["local"]["city"].split("(")[0],
                ATTR_REPORTED_LATITUDE: self.coordinator.data["local"]["latitude"],
                ATTR_REPORTED_LONGITUDE: self.coordinator.data["local"]["longitude"],
                ATTR_STATE: self.coordinator.data["state"]["name"],
                ATTR_ZIP_CODE: self.coordinator.data["local"]["zip"],
            }
        )

        if self._sensor_type in self.coordinator.data["state"]["data"]:
            states_key = self._sensor_type
        elif self._sensor_type in EXTENDED_SENSOR_TYPE_MAPPING:
            states_key = EXTENDED_SENSOR_TYPE_MAPPING[self._sensor_type]

        self._attrs[ATTR_STATE_REPORTS_THIS_WEEK] = self.coordinator.data["state"][
            "data"
        ][states_key]
        self._attrs[ATTR_STATE_REPORTS_LAST_WEEK] = self.coordinator.data["state"][
            "last_week_data"
        ][states_key]

        if self._sensor_type == SENSOR_TYPE_USER_TOTAL:
            self._state = sum(
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
            self._state = self.coordinator.data["local"][self._sensor_type]
