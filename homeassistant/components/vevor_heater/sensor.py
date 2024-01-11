"""Support for Vevor BLE heater sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Generic, TypeVar

from vevor_heater_ble.heater import (
    HeaterError,
    OperationalMode,
    OperationalStatus,
    VevorHeaterStatus,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VevorHeaterUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, kw_only=True)
class _VevorSensorEntityDescription(SensorEntityDescription, Generic[T]):
    extractor: Callable[[VevorHeaterStatus], T]


SENSORS: tuple = (
    _VevorSensorEntityDescription[OperationalMode](
        key="operational_mode",
        name="Operational Mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.operational_mode,
    ),
    _VevorSensorEntityDescription[OperationalStatus](
        key="operational_status",
        name="Operational Status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.operational_status,
    ),
    _VevorSensorEntityDescription[float](
        key="input_voltage",
        name="Source Voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.input_voltage,
    ),
    _VevorSensorEntityDescription[float](
        key="elevation",
        name="Elevation",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.elevation,
    ),
    _VevorSensorEntityDescription[int](
        key="target_temperature",
        name="Target temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.target_temperature,
    ),
    _VevorSensorEntityDescription[int](
        key="target_power_level",
        name="Target Power Level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.target_power_level,
    ),
    _VevorSensorEntityDescription[int](
        key="current_power_level",
        name="Current Power Level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.current_power_level,
    ),
    _VevorSensorEntityDescription[int](
        key="combustion_temperature",
        name="Combustion Chamber Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.combustion_temperature,
    ),
    _VevorSensorEntityDescription[int](
        key="room_temperature",
        name="Room Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.room_temperature,
    ),
    _VevorSensorEntityDescription[HeaterError](
        key="error",
        name="Error",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        extractor=lambda status: status.error,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Vevor BLE heater sensors."""

    coordinator: VevorHeaterUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("got sensors: %s", coordinator.data)

    async_add_entities(VevorHeaterSensor(coordinator, sensor) for sensor in SENSORS)


class VevorHeaterSensor(CoordinatorEntity[VevorHeaterUpdateCoordinator], SensorEntity):
    """Vevor BLE heater sensors for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VevorHeaterUpdateCoordinator,
        entity_description: _VevorSensorEntityDescription,
    ) -> None:
        """Populate the entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description: _VevorSensorEntityDescription = entity_description

        address = coordinator.get_device_address()

        self._attr_unique_id = f"{address}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            name=coordinator.data.name,
            manufacturer="Vevor",
            model="Vevor Heater",
            connections={(CONNECTION_BLUETOOTH, address)},
        )
        self._propagate_value()

    @callback
    def _propagate_value(self) -> None:
        """Update attrs from device."""
        if self.coordinator.data.status is not None:
            self._attr_native_value = self.entity_description.extractor(
                self.coordinator.data.status
            )
        else:
            self._attr_native_value = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attrs from device."""
        self._propagate_value()
        super()._handle_coordinator_update()
