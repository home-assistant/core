"""Support for the Environment Canada weather service."""
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_LOCATION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALERT_TYPES,
    ATTR_STATION,
    DOMAIN,
    SENSOR_TYPES,
)

ATTR_TIME = "alert time"

_LOGGER = logging.getLogger(__name__)


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return None
    if not re.fullmatch(r"[A-Z]{2}/s0000\d{3}", station):
        raise vol.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    async_add_entities(ECSensor(coordinator, desc) for desc in SENSOR_TYPES)
    async_add_entities(ECAlertSensor(coordinator, desc) for desc in ALERT_TYPES)


class ECSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, coordinator, description):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.ec_data = coordinator.ec_data

        self._attr_attribution = self.ec_data.metadata["attribution"]
        self._attr_name = f"{coordinator.config_entry.title} {description.name}"
        self._attr_unique_id = f"{self.ec_data.metadata['location']}-{description.key}"
        self._attr_extra_state_attributes = {
            ATTR_LOCATION: self.ec_data.metadata.get("location"),
            ATTR_STATION: self.ec_data.metadata.get("station"),
        }

    @property
    def native_value(self):
        """Update current conditions."""
        sensor_type = self.entity_description.key
        if sensor_type == "timestamp":
            return self.ec_data.metadata.get("timestamp")

        value = self.ec_data.conditions.get(sensor_type, {}).get("value")
        if sensor_type == "tendency":
            value = str(value).capitalize()
        elif isinstance(value, str) and len(value) > 255:
            value = value[:255]
            _LOGGER.info(
                "Value for %s truncated to 255 characters", self._attr_unique_id
            )
        return value


class ECAlertSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, coordinator, description):
        """Initialize the alert sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.ec_data = coordinator.ec_data

        self._attr_attribution = self.ec_data.metadata["attribution"]
        self._attr_name = f"{coordinator.config_entry.title} {description.name}"
        self._attr_unique_id = f"{self.ec_data.metadata['location']}-{description.key}"

    @property
    def native_value(self):
        """Return the state."""
        alert_name = self.entity_description.key
        value = self.ec_data.alerts.get(alert_name, {}).get("value")

        metadata = self.ec_data.metadata
        self._attr_extra_state_attributes = {
            ATTR_LOCATION: metadata.get("location"),
            ATTR_STATION: metadata.get("station"),
        }

        if value is None:
            return 0

        for index, alert in enumerate(value, start=1):
            self._attr_extra_state_attributes[f"alert_{index}"] = alert.get("title")
            self._attr_extra_state_attributes[f"alert_time_{index}"] = alert.get("date")

        return len(value)
