"""Sensors.

Two commands feed these: `0` for the electrical values, `3` for the counters.
An inverter that answered one but not the other reports `None` for the other.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from kaco_rs485 import STATUS_OPTIONS, InverterState, status_slug

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
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADDRESSES
from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator
from .entity import KacoRs485Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KacoSensorDescription(SensorEntityDescription):
    """A sensor plus how to pull its value out of an InverterState."""

    value_fn: Callable[[InverterState], float | str | None]


SENSORS: tuple[KacoSensorDescription, ...] = (
    KacoSensorDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.measured.ac_power_w if s.measured else None,
    ),
    KacoSensorDescription(
        key="ac_voltage",
        translation_key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.measured.ac_voltage_v if s.measured else None,
    ),
    KacoSensorDescription(
        key="ac_current",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.measured.ac_current_a if s.measured else None,
    ),
    KacoSensorDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.measured.dc_power_w if s.measured else None,
    ),
    KacoSensorDescription(
        key="dc_voltage",
        translation_key="dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.measured.dc_voltage_v if s.measured else None,
    ),
    KacoSensorDescription(
        key="dc_current",
        translation_key="dc_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.measured.dc_current_a if s.measured else None,
    ),
    KacoSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.measured.temperature_c if s.measured else None,
    ),
    KacoSensorDescription(
        key="daily_yield",
        translation_key="daily_yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: s.measured.daily_yield_wh if s.measured else None,
    ),
    KacoSensorDescription(
        key="total_yield",
        translation_key="total_yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.totals.total_yield_raw if s.totals else None,
    ),
    KacoSensorDescription(
        key="daily_peak_power",
        translation_key="daily_peak_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.totals.daily_peak_w if s.totals else None,
    ),
    KacoSensorDescription(
        key="total_uptime",
        translation_key="total_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.totals.total_uptime_hours if s.totals else None,
    ),
    KacoSensorDescription(
        key="daily_uptime",
        translation_key="daily_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.totals.daily_uptime_hours if s.totals else None,
    ),
    KacoSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_OPTIONS),
        value_fn=lambda s: status_slug(s.measured.status) if s.measured else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KacoRs485ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for every configured inverter."""
    coordinator = entry.runtime_data
    async_add_entities(
        KacoRs485Sensor(coordinator, address, description)
        for address in entry.data[CONF_ADDRESSES]
        for description in SENSORS
    )


class KacoRs485Sensor(KacoRs485Entity, SensorEntity):
    """One reading from one inverter."""

    entity_description: KacoSensorDescription

    def __init__(
        self,
        coordinator: KacoRs485Coordinator,
        address: int,
        description: KacoSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, address)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{address}_{description.key}"
        )

    @property
    @override
    def native_value(self) -> float | str | None:
        """Return the reading, or None if the inverter has not supplied it."""
        state = self.inverter
        return self.entity_description.value_fn(state) if state else None
