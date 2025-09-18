"""Support for Leneda sensors."""

from __future__ import annotations

import logging
from typing import Final

from leneda.obis_codes import get_obis_info

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SENSOR_TYPES, UNIT_TO_AGGREGATED_UNIT

_LOGGER = logging.getLogger(__name__)

# Error messages
ERROR_INVALID_SENSOR_TYPE: Final = "invalid_sensor_type"
ERROR_SENSOR_CREATION_FAILED: Final = "sensor_creation_failed"


class LenedaEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Leneda sensor."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator, metering_point: str, sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._metering_point: str = metering_point
        self._sensor_type: str = sensor_type

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
            obis_info.unit.lower(), obis_info.unit
        )
        self._attr_translation_key = sensor_type

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, metering_point)},
            "name": metering_point,
            "manufacturer": "Leneda",
            "model": "Metering point",
        }

        # Set additional attributes
        self._attr_extra_state_attributes = {
            "metering_point": metering_point,
            "sensor_type": sensor_type,
            "obis_code": self._obis_code,
            "obis_code_description": obis_info.description,
            "service_type": obis_info.service_type,
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
