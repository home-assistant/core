"""Support for Ambient Weather Station sensors."""
from __future__ import annotations

from homeassistant.components.sensor import DOMAIN as SENSOR, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    SENSOR_TYPES,
    TYPE_SOLARRADIATION,
    TYPE_SOLARRADIATION_LX,
    AmbientStation,
    AmbientWeatherEntity,
)
from .const import ATTR_LAST_DATA, ATTR_MONITORED_CONDITIONS, DATA_CLIENT, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in station[ATTR_MONITORED_CONDITIONS]:
            name, unit, kind, device_class = SENSOR_TYPES[condition]
            if kind == SENSOR:
                sensor_list.append(
                    AmbientWeatherSensor(
                        ambient,
                        mac_address,
                        station[ATTR_NAME],
                        condition,
                        name,
                        device_class,
                        unit,
                    )
                )

    async_add_entities(sensor_list)


class AmbientWeatherSensor(AmbientWeatherEntity, SensorEntity):
    """Define an Ambient sensor."""

    def __init__(
        self,
        ambient: AmbientStation,
        mac_address: str,
        station_name: str,
        sensor_type: str,
        sensor_name: str,
        device_class: str | None,
        unit: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            ambient, mac_address, station_name, sensor_type, sensor_name, device_class
        )

        self._attr_unit_of_measurement = unit

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        if self._sensor_type == TYPE_SOLARRADIATION_LX:
            # If the user requests the solarradiation_lx sensor, use the
            # value of the solarradiation sensor and apply a very accurate
            # approximation of converting sunlight W/m^2 to lx:
            w_m2_brightness_val = self._ambient.stations[self._mac_address][
                ATTR_LAST_DATA
            ].get(TYPE_SOLARRADIATION)

            if w_m2_brightness_val is None:
                self._attr_state = None
            else:
                self._attr_state = round(float(w_m2_brightness_val) / 0.0079)
        else:
            self._attr_state = self._ambient.stations[self._mac_address][
                ATTR_LAST_DATA
            ].get(self._sensor_type)
