"""Support for Vevor BLE heater sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VevorHeaterUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPINGS: dict[str, SensorEntityDescription] = {
    "operational_mode": SensorEntityDescription(
        key="operational_mode",
        name="Operational Mode",
        device_class=SensorDeviceClass.ENUM,
    ),
    "operational_status": SensorEntityDescription(
        key="operational_status",
        name="Operational Status",
        device_class=SensorDeviceClass.ENUM,
    ),
    "input_voltage": SensorEntityDescription(
        key="input_voltage",
        name="Source Voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "elevation": SensorEntityDescription(
        key="elevation",
        name="Elevation",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    "target_temperature": SensorEntityDescription(
        key="target_temperature",
        name="Target temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "target_power_level": SensorEntityDescription(
        key="target_power_level",
        name="Target Power Level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "current_power_level": SensorEntityDescription(
        key="current_power_level",
        name="Current Power Level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "combustion_temperature": SensorEntityDescription(
        key="combustion_temperature",
        name="Combustion Chamber Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "room_temperature": SensorEntityDescription(
        key="room_temperature",
        name="Room Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "error:": SensorEntityDescription(
        key="error",
        name="Error",
        device_class=SensorDeviceClass.ENUM,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airthings BLE sensors."""

    coordinator: VevorHeaterUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data)
    entities.extend(
        [VevorHeaterSensor(coordinator, sensor) for sensor in SENSORS_MAPPINGS.values()]
    )

    async_add_entities(entities)


class VevorHeaterSensor(CoordinatorEntity[VevorHeaterUpdateCoordinator], SensorEntity):
    """Airthings BLE sensors for the device."""

    def __init__(
        self,
        coordinator: VevorHeaterUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the airthings entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{coordinator.get_device_address()}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.get_device_address())}
        )
        self._propagate_value()

    @callback
    def _propagate_value(self) -> None:
        """Update attrs from device."""
        if self.coordinator.data.status is not None:
            self._attr_native_value = getattr(
                self.coordinator.data.status, self.entity_description.key
            )
        else:
            self._attr_native_value = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attrs from device."""
        self._propagate_value()
        super()._handle_coordinator_update()
