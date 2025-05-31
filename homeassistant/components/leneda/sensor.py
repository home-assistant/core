"""Support for Leneda sensors."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Final

from leneda.obis_codes import get_obis_info

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_METERING_POINTS, DOMAIN, SENSOR_TYPES, UNIT_TO_AGGREGATED_UNIT

_LOGGER = logging.getLogger(__name__)

# Error messages
ERROR_INVALID_SENSOR_TYPE: Final = "invalid_sensor_type"
ERROR_SENSOR_CREATION_FAILED: Final = "sensor_creation_failed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Leneda sensors."""
    coordinator = entry.runtime_data

    # Get metering points and selected sensors from config entry
    metering_points = entry.data[CONF_METERING_POINTS]
    selected_sensors = entry.options.get("selected_sensors", {})
    _LOGGER.debug("Setting up sensors for metering points: %s", metering_points)
    _LOGGER.debug("Selected sensors configuration: %s", selected_sensors)

    sensors: list[LenedaEnergySensor] = []
    for metering_point in metering_points:
        # Get the selected sensor types for this metering point
        # If no sensors are selected (old config), use all available sensors
        sensor_types = selected_sensors.get(metering_point, list(SENSOR_TYPES.keys()))
        _LOGGER.debug(
            "Setting up sensors for metering point %s: %s", metering_point, sensor_types
        )

        for sensor_type in sensor_types:
            if sensor_type not in SENSOR_TYPES:
                _LOGGER.error(
                    ERROR_SENSOR_CREATION_FAILED,
                    sensor_type,
                    metering_point,
                    "Invalid sensor type",
                )
                continue

            try:
                sensors.append(
                    LenedaEnergySensor(
                        coordinator,
                        metering_point,
                        sensor_type,
                        entry.data["energy_id"],
                    )
                )
            except (ValueError, KeyError, AttributeError) as err:
                _LOGGER.error(
                    ERROR_SENSOR_CREATION_FAILED,
                    sensor_type,
                    metering_point,
                    str(err),
                )

    _LOGGER.debug(
        "Created %d sensors for %d metering points", len(sensors), len(metering_points)
    )
    async_add_entities(sensors, True)


class LenedaEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Leneda sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        metering_point: str,
        sensor_type: str,
        energy_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._metering_point: str = metering_point
        self._sensor_type: str = sensor_type
        self._energy_id: str = energy_id

        # Get sensor configuration
        sensor_config = SENSOR_TYPES[sensor_type]
        self._obis_code = sensor_config["obis_code"]

        # Get OBIS code info
        obis_info = get_obis_info(self._obis_code)

        # Set sensor attributes
        self._attr_name = f"{obis_info.description} {metering_point}"
        self._attr_unique_id = f"{metering_point}_{sensor_type}"
        self._attr_device_class = sensor_config["device_class"]
        self._attr_state_class = sensor_config["state_class"]
        self._attr_native_unit_of_measurement = UNIT_TO_AGGREGATED_UNIT.get(
            obis_info.unit, obis_info.unit
        )
        self._attr_translation_key = sensor_type

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{energy_id}_{metering_point}")},
            "name": f"{energy_id} / {metering_point}",
            "manufacturer": "Leneda",
            "model": "Energy Meter",
        }

        # Set additional attributes
        self._attr_extra_state_attributes = {
            "metering_point": metering_point,
            "energy_id": energy_id,
            "sensor_type": sensor_type,
            "obis_code": self._obis_code,
            "obis_code_description": obis_info.description,
            "service_type": obis_info.service_type,
            "year": datetime.now().year,
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        meter_data = self.coordinator.data.get(self._metering_point)
        if not meter_data:
            return None

        return meter_data["values"].get(self._obis_code)

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        if not self.coordinator.data:
            return False

        meter_data = self.coordinator.data.get(self._metering_point)
        if not meter_data:
            return False

        # Check if the specific OBIS code has data
        return meter_data["values"].get(self._obis_code) is not None
