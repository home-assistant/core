"""Support for Ambient Weather Station binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    SENSOR_TYPES,
    TYPE_BATT1,
    TYPE_BATT2,
    TYPE_BATT3,
    TYPE_BATT4,
    TYPE_BATT5,
    TYPE_BATT6,
    TYPE_BATT7,
    TYPE_BATT8,
    TYPE_BATT9,
    TYPE_BATT10,
    TYPE_BATT_CO2,
    TYPE_BATTOUT,
    TYPE_PM25_BATT,
    TYPE_PM25IN_BATT,
    AmbientWeatherEntity,
)
from .const import ATTR_LAST_DATA, ATTR_MONITORED_CONDITIONS, DATA_CLIENT, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in station[ATTR_MONITORED_CONDITIONS]:
            name, _, kind, device_class = SENSOR_TYPES[condition]
            if kind == BINARY_SENSOR:
                binary_sensor_list.append(
                    AmbientWeatherBinarySensor(
                        ambient,
                        mac_address,
                        station[ATTR_NAME],
                        condition,
                        name,
                        device_class,
                    )
                )

    async_add_entities(binary_sensor_list)


class AmbientWeatherBinarySensor(AmbientWeatherEntity, BinarySensorEntity):
    """Define an Ambient binary sensor."""

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the entity."""
        state = self._ambient.stations[self._mac_address][ATTR_LAST_DATA].get(
            self._sensor_type
        )

        if self._sensor_type in (
            TYPE_BATT1,
            TYPE_BATT10,
            TYPE_BATT2,
            TYPE_BATT3,
            TYPE_BATT4,
            TYPE_BATT5,
            TYPE_BATT6,
            TYPE_BATT7,
            TYPE_BATT8,
            TYPE_BATT9,
            TYPE_BATT_CO2,
            TYPE_BATTOUT,
            TYPE_PM25_BATT,
            TYPE_PM25IN_BATT,
        ):
            self._attr_is_on = state == 0
        else:
            self._attr_is_on = state == 1
