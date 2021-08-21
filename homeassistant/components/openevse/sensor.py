"""Support for monitoring an OpenEVSE Charger."""
from __future__ import annotations

import logging

import openevsewifi
from requests import RequestException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
    TIME_MINUTES,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "status": ["Charging Status", None, None],
    "charge_time": ["Charge Time Elapsed", TIME_MINUTES, None],
    "ambient_temp": ["Ambient Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE],
    "ir_temp": ["IR Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE],
    "rtc_temp": ["RTC Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE],
    "usage_session": ["Usage this Session", ENERGY_KILO_WATT_HOUR, None],
    "usage_total": ["Total Usage", ENERGY_KILO_WATT_HOUR, None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["status"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the OpenEVSE sensor."""
    host = config[CONF_HOST]
    monitored_variables = config[CONF_MONITORED_VARIABLES]

    charger = openevsewifi.Charger(host)

    entities = [
        OpenEVSESensor(charger, description)
        for description in SENSOR_TYPES
        if description.key in monitored_variables
    ]

    add_entities(entities, True)


class OpenEVSESensor(SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    def __init__(self, charger, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.charger = charger
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._attr_device_class = SENSOR_TYPES[sensor_type][2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self._unit_of_measurement

    def update(self):
        """Get the monitored data from the charger."""
        try:
            sensor_type = self.entity_description.key
            if sensor_type == "status":
                self._attr_native_value = self.charger.getStatus()
            elif sensor_type == "charge_time":
                self._attr_native_value = self.charger.getChargeTimeElapsed() / 60
            elif sensor_type == "ambient_temp":
                self._attr_native_value = self.charger.getAmbientTemperature()
            elif sensor_type == "ir_temp":
                self._attr_native_value = self.charger.getIRTemperature()
            elif sensor_type == "rtc_temp":
                self._attr_native_value = self.charger.getRTCTemperature()
            elif sensor_type == "usage_session":
                self._attr_native_value = float(self.charger.getUsageSession()) / 1000
            elif sensor_type == "usage_total":
                self._attr_native_value = float(self.charger.getUsageTotal()) / 1000
            else:
                self._attr_native_value = "Unknown"
        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
