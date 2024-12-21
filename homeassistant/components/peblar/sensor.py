"""Support for Peblar sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from peblar import PeblarMeter, PeblarUserConfiguration

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PeblarConfigEntry, PeblarMeterDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class PeblarSensorDescription(SensorEntityDescription):
    """Describe an Peblar sensor."""

    has_fn: Callable[[PeblarUserConfiguration], bool] = lambda _: True
    value_fn: Callable[[PeblarMeter], int | None]


DESCRIPTIONS: tuple[PeblarSensorDescription, ...] = (
    PeblarSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases == 1,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda x: x.current_phase_1,
    ),
    PeblarSensorDescription(
        key="current_phase_1",
        translation_key="current_phase_1",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases >= 2,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda x: x.current_phase_1,
    ),
    PeblarSensorDescription(
        key="current_phase_2",
        translation_key="current_phase_2",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases >= 2,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda x: x.current_phase_2,
    ),
    PeblarSensorDescription(
        key="current_phase_3",
        translation_key="current_phase_3",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases == 3,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda x: x.current_phase_3,
    ),
    PeblarSensorDescription(
        key="energy_session",
        translation_key="energy_session",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda x: x.energy_session,
    ),
    PeblarSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda x: x.energy_total,
    ),
    PeblarSensorDescription(
        key="power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.power_total,
    ),
    PeblarSensorDescription(
        key="power_phase_1",
        translation_key="power_phase_1",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases >= 2,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.power_phase_1,
    ),
    PeblarSensorDescription(
        key="power_phase_2",
        translation_key="power_phase_2",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases >= 2,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.power_phase_2,
    ),
    PeblarSensorDescription(
        key="power_phase_3",
        translation_key="power_phase_3",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases == 3,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.power_phase_3,
    ),
    PeblarSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases == 1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.voltage_phase_1,
    ),
    PeblarSensorDescription(
        key="voltage_phase_1",
        translation_key="voltage_phase_1",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases >= 2,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.voltage_phase_1,
    ),
    PeblarSensorDescription(
        key="voltage_phase_2",
        translation_key="voltage_phase_2",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases >= 2,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.voltage_phase_2,
    ),
    PeblarSensorDescription(
        key="voltage_phase_3",
        translation_key="voltage_phase_3",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases == 3,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.voltage_phase_3,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar sensors based on a config entry."""
    async_add_entities(
        PeblarSensorEntity(entry, description)
        for description in DESCRIPTIONS
        if description.has_fn(entry.runtime_data.user_configuraton_coordinator.data)
    )


class PeblarSensorEntity(
    CoordinatorEntity[PeblarMeterDataUpdateCoordinator], SensorEntity
):
    """Defines a Peblar sensor."""

    entity_description: PeblarSensorDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PeblarConfigEntry,
        description: PeblarSensorDescription,
    ) -> None:
        """Initialize the Peblar entity."""
        super().__init__(entry.runtime_data.meter_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
