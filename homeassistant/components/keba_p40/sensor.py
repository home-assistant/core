"""Sensor platform for KEBA P40."""

from collections.abc import Callable
from dataclasses import dataclass

from keba_kecontact_p40 import Wallbox, WallboxState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import KebaP40ConfigEntry
from .entity import KebaP40Entity

PARALLEL_UPDATES = 0


def _line_current(wallbox: Wallbox, index: int) -> float | None:
    if wallbox.meter is None or len(wallbox.meter.lines) <= index:
        return None
    value = wallbox.meter.lines[index].current_ma
    return None if value is None else value / 1000


def _line_voltage(wallbox: Wallbox, index: int) -> int | None:
    if wallbox.meter is None or len(wallbox.meter.lines) <= index:
        return None
    return wallbox.meter.lines[index].voltage_v


@dataclass(frozen=True, kw_only=True)
class KebaP40SensorDescription(SensorEntityDescription):
    """Describes a KEBA P40 sensor."""

    value_fn: Callable[[Wallbox], StateType]


SENSORS: tuple[KebaP40SensorDescription, ...] = (
    KebaP40SensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value.lower() for state in WallboxState],
        value_fn=lambda wb: wb.state.value.lower() if wb.state else None,
    ),
    KebaP40SensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda wb: (
            None
            if wb.meter is None or wb.meter.power_mw is None
            else wb.meter.power_mw / 1000
        ),
    ),
    KebaP40SensorDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda wb: (
            None
            if wb.meter is None or wb.meter.energy_mwh is None
            else wb.meter.energy_mwh / 1_000_000
        ),
    ),
    KebaP40SensorDescription(
        key="current_offered",
        translation_key="current_offered",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda wb: (
            None
            if wb.meter is None or wb.meter.current_offered_ma is None
            else wb.meter.current_offered_ma / 1000
        ),
    ),
    KebaP40SensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda wb: (
            None
            if wb.meter is None or wb.meter.temperature_centi_c is None
            else wb.meter.temperature_centi_c / 100
        ),
    ),
    KebaP40SensorDescription(
        key="power_factor",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: (
            None
            if wb.meter is None or wb.meter.power_factor is None
            else wb.meter.power_factor / 10
        ),
    ),
    KebaP40SensorDescription(
        key="max_current",
        translation_key="max_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: (
            None if wb.max_current_ma is None else wb.max_current_ma / 1000
        ),
    ),
    KebaP40SensorDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: wb.error_code,
    ),
    KebaP40SensorDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: _line_voltage(wb, 0),
    ),
    KebaP40SensorDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: _line_voltage(wb, 1),
    ),
    KebaP40SensorDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: _line_voltage(wb, 2),
    ),
    KebaP40SensorDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: _line_current(wb, 0),
    ),
    KebaP40SensorDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: _line_current(wb, 1),
    ),
    KebaP40SensorDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda wb: _line_current(wb, 2),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaP40ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA P40 sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        KebaP40Sensor(coordinator, description) for description in SENSORS
    )


class KebaP40Sensor(KebaP40Entity, SensorEntity):
    """A KEBA P40 sensor."""

    entity_description: KebaP40SensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._wallbox)
