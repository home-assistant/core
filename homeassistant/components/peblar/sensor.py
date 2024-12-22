"""Support for Peblar sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from peblar import PeblarUserConfiguration

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    PEBLAR_CHARGE_LIMITER_TO_HOME_ASSISTANT,
    PEBLAR_CP_STATE_TO_HOME_ASSISTANT,
)
from .coordinator import PeblarConfigEntry, PeblarData, PeblarDataUpdateCoordinator
from .entity import PeblarEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PeblarSensorDescription(SensorEntityDescription):
    """Describe a Peblar sensor."""

    has_fn: Callable[[PeblarUserConfiguration], bool] = lambda _: True
    value_fn: Callable[[PeblarData], datetime | int | str | None]


DESCRIPTIONS: tuple[PeblarSensorDescription, ...] = (
    PeblarSensorDescription(
        key="cp_state",
        translation_key="cp_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(PEBLAR_CP_STATE_TO_HOME_ASSISTANT.values()),
        value_fn=lambda x: PEBLAR_CP_STATE_TO_HOME_ASSISTANT[x.ev.cp_state],
    ),
    PeblarSensorDescription(
        key="charge_current_limit_source",
        translation_key="charge_current_limit_source",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(PEBLAR_CHARGE_LIMITER_TO_HOME_ASSISTANT.values()),
        value_fn=lambda x: PEBLAR_CHARGE_LIMITER_TO_HOME_ASSISTANT[
            x.ev.charge_current_limit_source
        ],
    ),
    PeblarSensorDescription(
        key="current_total",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda x: x.meter.current_total,
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
        value_fn=lambda x: x.meter.current_phase_1,
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
        value_fn=lambda x: x.meter.current_phase_2,
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
        value_fn=lambda x: x.meter.current_phase_3,
    ),
    PeblarSensorDescription(
        key="energy_session",
        translation_key="energy_session",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda x: x.meter.energy_session,
    ),
    PeblarSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda x: x.meter.energy_total,
    ),
    PeblarSensorDescription(
        key="power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.meter.power_total,
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
        value_fn=lambda x: x.meter.power_phase_1,
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
        value_fn=lambda x: x.meter.power_phase_2,
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
        value_fn=lambda x: x.meter.power_phase_3,
    ),
    PeblarSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda x: x.connected_phases == 1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.meter.voltage_phase_1,
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
        value_fn=lambda x: x.meter.voltage_phase_1,
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
        value_fn=lambda x: x.meter.voltage_phase_2,
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
        value_fn=lambda x: x.meter.voltage_phase_3,
    ),
    PeblarSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda x: (
            utcnow().replace(microsecond=0) - timedelta(seconds=x.system.uptime)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar sensors based on a config entry."""
    async_add_entities(
        PeblarSensorEntity(
            entry=entry,
            coordinator=entry.runtime_data.data_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
        if description.has_fn(entry.runtime_data.user_configuration_coordinator.data)
    )


class PeblarSensorEntity(PeblarEntity[PeblarDataUpdateCoordinator], SensorEntity):
    """Defines a Peblar sensor."""

    entity_description: PeblarSensorDescription

    @property
    def native_value(self) -> datetime | int | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
