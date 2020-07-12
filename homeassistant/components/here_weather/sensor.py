"""Support for the HERE Destination Weather service."""
import logging
from typing import Dict, Optional, Union

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import HEREWeatherData
from .const import DOMAIN, SENSOR_TYPES
from .utils import convert_unit_of_measurement_if_needed, get_attribute_from_here_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Add here_weather entities from a config_entry."""
    here_weather_data = hass.data[DOMAIN][config_entry.entry_id]

    sensors_to_add = []
    for sensor_type in SENSOR_TYPES:
        if sensor_type == config_entry.data[CONF_MODE]:
            for weather_attribute in SENSOR_TYPES[sensor_type]:
                sensors_to_add.append(
                    HEREDestinationWeatherSensor(
                        config_entry.data[CONF_NAME],
                        here_weather_data,
                        sensor_type,
                        weather_attribute,
                    )
                )
    async_add_entities(sensors_to_add, True)


class HEREDestinationWeatherSensor(Entity):
    """Implementation of an HERE Destination Weather sensor."""

    def __init__(
        self,
        name: str,
        here_data: HEREWeatherData,
        sensor_type: str,
        weather_attribute: str,
        sensor_number: int = 0,  # Additional supported offsets will be added in a separate PR
    ) -> None:
        """Initialize the sensor."""
        self._base_name = name
        self._name_suffix = SENSOR_TYPES[sensor_type][weather_attribute]["name"]
        self._here_data = here_data
        self._sensor_type = sensor_type
        self._sensor_number = sensor_number
        self._weather_attribute = weather_attribute
        self._unit_of_measurement = convert_unit_of_measurement_if_needed(
            self._here_data.units,
            SENSOR_TYPES[sensor_type][weather_attribute]["unit_of_measurement"],
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._base_name} {self._name_suffix}"

    @property
    def unique_id(self):
        """Set unique_id for sensor."""
        return self.name

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return get_attribute_from_here_data(
            self._here_data.coordinator.data,
            self._weather_attribute,
            self._sensor_number,
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(
        self,
    ) -> Optional[Dict[str, Union[None, float, str, bool]]]:
        """Return the state attributes."""
        return None

    @property
    def available(self):
        """Could the api be accessed during the last update call."""
        return self._here_data.coordinator.last_update_success

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def device_info(self) -> dict:
        """Return a device description for device registry."""

        return {
            "identifiers": {(DOMAIN, self._base_name)},
            "name": self._base_name,
            "manufacturer": "here.com",
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._here_data.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Get the latest data from HERE."""
        await self._here_data.coordinator.async_request_refresh()
