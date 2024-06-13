"""Sensoterra devices."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import CONFIGURATION_URL, DOMAIN
from .coordinator import SensoterraCoordinator, SensoterraSensor

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up Sensoterra sensor."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    def _add_devices(devices: dict[str, SensoterraSensor]) -> None:
        sensors = [
            SensoterraEntity(coordinator, sensor_id, sensor)
            for sensor_id, sensor in devices.items()
            if sensor.type
            in ["MOISTURE", "SI", "TEMPERATURE", "BATTERY", "RSSI", "LASTSEEN"]
        ]
        async_add_devices(sensors)

    coordinator.add_devices_callback = _add_devices

    _add_devices(coordinator.data)


class SensoterraEntity(CoordinatorEntity, SensorEntity):
    """Sensoterra sensor like a soil moisture or temperature sensor."""

    def __init__(
        self,
        coordinator: SensoterraCoordinator,
        sensor_id: str,
        sensor: SensoterraSensor,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, context=sensor_id)

        self.sensor_id = sensor_id
        self.sensor = sensor

        self._attr_has_entity_name = True
        self._attr_unique_id = self.sensor_id
        if sensor.type != "LASTSEEN":
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attrs_native_value = float
        self._attr_suggested_display_precision = 0
        if sensor.soil is not None:
            self._attr_extra_state_attributes = {
                "soil_type": sensor.soil,
            }

        if sensor.type == "MOISTURE":
            self._attr_device_class = SensorDeviceClass.MOISTURE
            if sensor.depth is None:
                self._attr_translation_key = "soil_moisture"
            else:
                self._attr_translation_key = "soil_moisture_at_cm"
                self._attr_translation_placeholders = {"depth": sensor.depth}
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif sensor.type == "SI":
            if sensor.depth is None:
                self._attr_name = "SI"
            else:
                self._attr_name = "SI @ {sensor.depth} cm"
            self._attr_suggested_display_precision = 1
        elif sensor.type == "TEMPERATURE":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif sensor.type == "BATTERY":
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif sensor.type == "RSSI":
            self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
            self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif sensor.type == "LASTSEEN":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_translation_key = "last_seen"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        else:
            raise UpdateFailed(f"Unknown sensor type {sensor.type}")

        if sensor.value is not None:
            self._attr_native_value = sensor.value

        # If True, a state change will be triggered anytime the state property is
        # updated, not just when the value changes.
        self._attr_force_update = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        sensor: SensoterraSensor = self.coordinator.data[self.sensor_id]
        if sensor.value is not None:
            self._attr_native_value = sensor.value
            self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Information about the Sensoterra probe."""
        return {
            "identifiers": {(DOMAIN, self.sensor.serial)},
            "name": self.sensor.name,
            "model": self.sensor.sku,
            "manufacturer": "Sensoterra",
            "serial_number": self.sensor.serial,
            "suggested_area": self.sensor.location,  # area_id could also be set
            "configuration_url": CONFIGURATION_URL,
        }
