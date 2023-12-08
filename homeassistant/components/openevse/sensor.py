"""Support for monitoring an OpenEVSE Charger."""
from __future__ import annotations

import logging

import openevsewifi
from requests import RequestException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status",
        name="Charging Status",
    ),
    SensorEntityDescription(
        key="charge_time",
        name="Charge Time Elapsed",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ambient_temp",
        name="Ambient Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ir_temp",
        name="IR Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rtc_temp",
        name="RTC Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="usage_session",
        name="Usage this Session",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="usage_total",
        name="Total Usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["status"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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

    def __init__(self, charger, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.charger = charger

    def update(self) -> None:
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
