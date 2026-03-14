"""Sensor platform for Specialized Turbo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from specialized_turbo import AssistLevel, TelemetrySnapshot

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
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
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SpecializedTurboConfigEntry
from .const import DOMAIN
from .coordinator import SpecializedTurboCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SpecializedSensorEntityDescription(SensorEntityDescription):
    """Describes a Specialized Turbo sensor entity."""

    value_fn: Callable[[TelemetrySnapshot], Any]


def _assist_level_name(snap: TelemetrySnapshot) -> str | None:
    """Return assist level as a human-readable string."""
    level = snap.motor.assist_level
    if level is None:
        return None
    if isinstance(level, AssistLevel):
        return str(level.name.capitalize())
    return str(level)


SENSOR_DESCRIPTIONS: tuple[SpecializedSensorEntityDescription, ...] = (
    # --- Battery ---
    SpecializedSensorEntityDescription(
        key="battery_charge_percent",
        translation_key="battery_charge_percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.battery.charge_pct,
    ),
    SpecializedSensorEntityDescription(
        key="battery_capacity_wh",
        translation_key="battery_capacity_wh",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.battery.capacity_wh,
    ),
    SpecializedSensorEntityDescription(
        key="battery_remaining_wh",
        translation_key="battery_remaining_wh",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.battery.remaining_wh,
    ),
    SpecializedSensorEntityDescription(
        key="battery_health",
        translation_key="battery_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery.health_pct,
    ),
    SpecializedSensorEntityDescription(
        key="battery_temp",
        translation_key="battery_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery.temp_c,
    ),
    SpecializedSensorEntityDescription(
        key="battery_charge_cycles",
        translation_key="battery_charge_cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery.charge_cycles,
    ),
    SpecializedSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery.voltage_v,
    ),
    SpecializedSensorEntityDescription(
        key="battery_current",
        translation_key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery.current_a,
    ),
    # --- Motor / Rider ---
    SpecializedSensorEntityDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.motor.speed_kmh,
    ),
    SpecializedSensorEntityDescription(
        key="rider_power",
        translation_key="rider_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.motor.rider_power_w,
    ),
    SpecializedSensorEntityDescription(
        key="motor_power",
        translation_key="motor_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.motor.motor_power_w,
    ),
    SpecializedSensorEntityDescription(
        key="cadence",
        translation_key="cadence",
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.motor.cadence_rpm,
    ),
    SpecializedSensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.motor.odometer_km,
    ),
    SpecializedSensorEntityDescription(
        key="motor_temp",
        translation_key="motor_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.motor.motor_temp_c,
    ),
    SpecializedSensorEntityDescription(
        key="assist_level",
        translation_key="assist_level",
        value_fn=_assist_level_name,
    ),
    # --- Settings (informational) ---
    SpecializedSensorEntityDescription(
        key="assist_eco_pct",
        translation_key="assist_eco_pct",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.settings.assist_lev1_pct,
    ),
    SpecializedSensorEntityDescription(
        key="assist_trail_pct",
        translation_key="assist_trail_pct",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.settings.assist_lev2_pct,
    ),
    SpecializedSensorEntityDescription(
        key="assist_turbo_pct",
        translation_key="assist_turbo_pct",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.settings.assist_lev3_pct,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpecializedTurboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Specialized Turbo sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SpecializedTurboSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class SpecializedTurboSensor(
    PassiveBluetoothCoordinatorEntity[SpecializedTurboCoordinator],
    SensorEntity,
):
    """One telemetry field from a Specialized Turbo bike."""

    entity_description: SpecializedSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpecializedTurboCoordinator,
        description: SpecializedSensorEntityDescription,
        entry: SpecializedTurboConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(entry.data['address'])}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_mac(entry.data["address"]))},
            name=entry.title,
            manufacturer="Specialized",
            model="Turbo",
        )

    @property
    def native_value(self) -> StateType:
        """Return the sensor value from the coordinator's snapshot."""
        return self.entity_description.value_fn(self.coordinator.snapshot)

    @property
    def available(self) -> bool:
        """Return True if the bike is connected."""
        return self.coordinator.connected
