"""Sensor platform for the HERE Destination Weather service."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SENSOR_TYPES
from .utils import convert_unit_of_measurement_if_needed, get_attribute_from_here_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Add here_weather entities from a config_entry."""
    here_weather_data_dict = hass.data[DOMAIN][config_entry.entry_id]

    sensors_to_add = []
    for sensor_type in SENSOR_TYPES:
        for weather_attribute in SENSOR_TYPES[sensor_type]:
            sensors_to_add.append(
                HEREDestinationWeatherSensor(
                    config_entry,
                    here_weather_data_dict[sensor_type].coordinator,
                    sensor_type,
                    weather_attribute,
                )
            )
    async_add_entities(sensors_to_add, True)


class HEREDestinationWeatherSensor(CoordinatorEntity):
    """Implementation of an HERE Destination Weather sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        sensor_type: str,
        weather_attribute: str,
        sensor_number: int = 0,  # Additional supported offsets will be added in a separate PR
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._base_name = config_entry.data[CONF_NAME]
        self._name_suffix = SENSOR_TYPES[sensor_type][weather_attribute]["name"]
        self._latitude = config_entry.data[CONF_LATITUDE]
        self._longitude = config_entry.data[CONF_LONGITUDE]
        self._sensor_type = sensor_type
        self._sensor_number = sensor_number
        self._weather_attribute = weather_attribute
        self._unit_of_measurement = convert_unit_of_measurement_if_needed(
            self.coordinator.hass.config.units.name,
            SENSOR_TYPES[sensor_type][weather_attribute]["unit_of_measurement"],
        )
        self._unique_id = "".join(
            f"{self._base_name}_{self._sensor_type}_{self._name_suffix}_{self._sensor_number}".lower().split()
        )

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._base_name} {self._sensor_type} {self._name_suffix} {self._sensor_number}"

    @property
    def unique_id(self) -> str:
        """Set unique_id for sensor."""
        return self._unique_id

    @property
    def state(self) -> StateType:
        """Return the state of the device."""
        return get_attribute_from_here_data(
            self.coordinator.data,
            self._weather_attribute,
            self._sensor_number,
        )

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""

        return {
            "identifiers": {(DOMAIN, self._base_name)},
            "name": self._base_name,
            "manufacturer": "here.com",
            "entry_type": "service",
        }
