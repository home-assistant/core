"""Sensor platform for Besen BS20."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import override

from besen_bs20.models import BesenBS20Data

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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

from . import BesenBS20ConfigEntry
from .const import (
    CHARGING_STATUS,
    CHARGING_STATUS_DESCRIPTIONS,
    CURRENT_STATE,
    ERRORS,
    OUTPUT_STATE,
    PLUG_STATE,
)
from .coordinator import BesenBS20Coordinator
from .entity import BesenBS20Entity

PARALLEL_UPDATES = 0

SensorValue = Callable[[BesenBS20Data], StateType | date | datetime | Decimal]


@dataclass(frozen=True, kw_only=True)
class BesenSensorEntityDescription(SensorEntityDescription):
    """Besen sensor description."""

    value_fn: SensorValue
    options: list[str] | None = None


SENSORS: tuple[BesenSensorEntityDescription, ...] = (
    BesenSensorEntityDescription(
        key="current_power",
        name="Current Energy",
        value_fn=lambda data: data.charge.current_energy,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BesenSensorEntityDescription(
        key="total_energy",
        name="Total Energy",
        value_fn=lambda data: data.charge.current_amount,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BesenSensorEntityDescription(
        key="session_energy",
        name="Session Energy",
        value_fn=lambda data: data.charge.total_energy,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    BesenSensorEntityDescription(
        key="temperature",
        name="Temperature",
        value_fn=lambda data: data.charge.inner_temp_c,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BesenSensorEntityDescription(
        key="outer_temperature",
        name="Outer Temperature",
        value_fn=lambda data: data.charge.outer_temp,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BesenSensorEntityDescription(
        key="l1_voltage",
        name="L1 Voltage",
        value_fn=lambda data: data.charge.l1_voltage,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="l1_current",
        name="L1 Amperage",
        value_fn=lambda data: data.charge.l1_amperage,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="l2_voltage",
        name="L2 Voltage",
        value_fn=lambda data: data.charge.l2_voltage,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="l2_current",
        name="L2 Amperage",
        value_fn=lambda data: data.charge.l2_amperage,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="l3_voltage",
        name="L3 Voltage",
        value_fn=lambda data: data.charge.l3_voltage,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="l3_current",
        name="L3 Amperage",
        value_fn=lambda data: data.charge.l3_amperage,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="error_state",
        name="Error State",
        value_fn=lambda data: data.charge.error_details,
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(ERRORS.values())),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="charging_status",
        name="Status",
        value_fn=lambda data: data.charge.charging_status,
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(CHARGING_STATUS.values())),
    ),
    BesenSensorEntityDescription(
        key="charging_message",
        name="Message",
        value_fn=lambda data: data.charge.charging_status_description,
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(CHARGING_STATUS_DESCRIPTIONS.values())),
    ),
    BesenSensorEntityDescription(
        key="plug_state",
        name="Plug State",
        value_fn=lambda data: data.charge.plug_state,
        device_class=SensorDeviceClass.ENUM,
        options=PLUG_STATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="output_state",
        name="Output State",
        value_fn=lambda data: data.charge.output_state,
        device_class=SensorDeviceClass.ENUM,
        options=OUTPUT_STATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="current_state",
        name="Current State",
        value_fn=lambda data: data.charge.current_state,
        device_class=SensorDeviceClass.ENUM,
        options=CURRENT_STATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BesenSensorEntityDescription(
        key="rssi",
        name="RSSI",
        value_fn=lambda data: data.config.rssi,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BesenSensorEntityDescription(
        key="system_time",
        name="System Time",
        value_fn=lambda data: data.config.system_time,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BesenSensorEntityDescription(
        key="software_version",
        name="Software Version",
        value_fn=lambda data: data.info.software_version,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Besen BS20 sensors."""

    coordinator = entry.runtime_data.coordinator
    data = coordinator.data or coordinator.client.state
    sensors = [
        BesenBS20Sensor(coordinator, description)
        for description in SENSORS
        if data.info.phases == 3
        or description.key
        not in {"l2_voltage", "l2_current", "l3_voltage", "l3_current"}
    ]
    async_add_entities(sensors)


class BesenBS20Sensor(BesenBS20Entity, SensorEntity):
    """Besen BS20 sensor."""

    entity_description: BesenSensorEntityDescription

    def __init__(
        self,
        coordinator: BesenBS20Coordinator,
        description: BesenSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the sensor value."""

        data = self.coordinator.data or self.coordinator.client.state
        return self.entity_description.value_fn(data)

    @property
    @override
    def available(self) -> bool:
        """Return entity availability."""

        return super().available and self.native_value is not None

    @property
    @override
    def options(self) -> list[str] | None:
        """Return enum options."""

        return self.entity_description.options
