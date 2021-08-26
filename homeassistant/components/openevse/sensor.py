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
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status",
        name="Charging Status",
    ),
    SensorEntityDescription(
        key="charge_time",
        name="Charge Time Elapsed",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="ambient_temp",
        name="Ambient Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="ir_temp",
        name="IR Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="rtc_temp",
        name="RTC Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="usage_session",
        name="Usage this Session",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    SensorEntityDescription(
        key="usage_total",
        name="Total Usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OpenEVSE sensors."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OpenEVSE sensors."""
    host = entry.data[CONF_HOST]

    charger = openevsewifi.Charger(host)

    entities = [OpenEVSESensor(charger, description) for description in SENSOR_TYPES]

    async_add_entities(entities)


class OpenEVSESensor(SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    def __init__(self, charger, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.charger = charger

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
