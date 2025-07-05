"""Sensor platform for Eway integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DURATION,
    ATTR_ERROR_CODE,
    ATTR_GEN_POWER,
    ATTR_GEN_POWER_TODAY,
    ATTR_GEN_POWER_TOTAL,
    ATTR_GRID_FREQ,
    ATTR_GRID_VOLTAGE,
    ATTR_INPUT_CURRENT,
    ATTR_INPUT_VOLTAGE,
    ATTR_TEMPERATURE,
    DOMAIN,
)
from .coordinator import EwayDataUpdateCoordinator


@dataclass(frozen=True)
class EwaySensorEntityDescription(SensorEntityDescription):
    """Describes Eway sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None


SENSOR_TYPES: tuple[EwaySensorEntityDescription, ...] = (
    EwaySensorEntityDescription(
        key=ATTR_GEN_POWER,
        name="Generation Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=None,
        entity_registry_enabled_default=True,
        value_fn=lambda data: data.get("gen_power"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_GRID_VOLTAGE,
        name="Grid Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("grid_voltage"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_INPUT_VOLTAGE,
        name="Input Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("input_voltage"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_INPUT_CURRENT,
        name="Input Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("input_current"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_GRID_FREQ,
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("grid_freq"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        value_fn=lambda data: data.get("temperature"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_GEN_POWER_TODAY,
        name="Energy Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=None,
        entity_registry_enabled_default=True,
        value_fn=lambda data: data.get("gen_power_today"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_GEN_POWER_TOTAL,
        name="Energy Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=None,
        entity_registry_enabled_default=True,
        value_fn=lambda data: data.get("gen_power_total"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_ERROR_CODE,
        name="Error Code",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        value_fn=lambda data: data.get("error_code"),
    ),
    EwaySensorEntityDescription(
        key=ATTR_DURATION,
        name="Working Duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("duration"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eway sensor based on a config entry."""
    coordinator: EwayDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [EwaySensor(coordinator, description) for description in SENSOR_TYPES]

    async_add_entities(entities)


class EwaySensor(CoordinatorEntity[EwayDataUpdateCoordinator], SensorEntity):
    """Representation of an Eway sensor."""

    entity_description: EwaySensorEntityDescription

    def __init__(
        self,
        coordinator: EwayDataUpdateCoordinator,
        description: EwaySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
