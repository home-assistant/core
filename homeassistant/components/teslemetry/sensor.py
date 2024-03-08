"""Sensor platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import (
    TeslemetryEnergyEntity,
    TeslemetryVehicleEntity,
    TeslemetryWallConnectorEntity,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData


@callback
def minutes_to_datetime(value: StateType) -> datetime | None:
    """Convert relative minutes into absolute datetime."""
    if isinstance(value, (int, float)) and value > 0:
        return dt_util.now() + timedelta(minutes=value)
    return None


@dataclass(frozen=True, kw_only=True)
class TeslemetrySensorEntityDescription(SensorEntityDescription):
    """Describes Teslemetry Sensor entity."""

    value_fn: Callable[[StateType], StateType | datetime] = lambda x: x


VEHICLE_DESCRIPTIONS: tuple[TeslemetrySensorEntityDescription, ...] = (
    TeslemetrySensorEntityDescription(
        key="charge_state_usable_battery_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_charge_energy_added",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_charger_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_charger_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_charger_actual_current",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_charge_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_minutes_to_full_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=minutes_to_datetime,
    ),
    TeslemetrySensorEntityDescription(
        key="charge_state_battery_range",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_shift_state",
        icon="mdi:car-shift-pattern",
        options=["p", "d", "r", "n"],
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: x.lower() if isinstance(x, str) else x,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="vehicle_state_odometer",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="vehicle_state_tpms_pressure_fl",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="vehicle_state_tpms_pressure_fr",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="vehicle_state_tpms_pressure_rl",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="vehicle_state_tpms_pressure_rr",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="climate_state_inside_temp",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    TeslemetrySensorEntityDescription(
        key="climate_state_outside_temp",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    TeslemetrySensorEntityDescription(
        key="climate_state_driver_temp_setting",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="climate_state_passenger_temp_setting",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_active_route_traffic_minutes_delay",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_active_route_energy_at_arrival",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_active_route_miles_to_arrival",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_active_route_minutes_to_arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=minutes_to_datetime,
    ),
    TeslemetrySensorEntityDescription(
        key="drive_state_active_route_destination",
        icon="mdi:map-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENERGY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="solar_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="energy_left",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="total_pack_energy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-high",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="percentage_charged",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="battery_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:home-battery",
    ),
    SensorEntityDescription(
        key="load_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="grid_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:transmission-tower",
    ),
    SensorEntityDescription(
        key="grid_services_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:transmission-tower",
    ),
    SensorEntityDescription(
        key="generator_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:generator-stationary",
        entity_registry_enabled_default=False,
    ),
)

WALL_CONNECTOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="wall_connector_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:ev-station",
    ),
    SensorEntityDescription(
        key="wall_connector_fault_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:ev-station",
    ),
    SensorEntityDescription(
        key="wall_connector_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:ev-station",
    ),
    SensorEntityDescription(
        key="vin",
        icon="mdi:car-electric",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Teslemetry sensor platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        chain(
            (  # Add vehicles
                TeslemetryVehicleSensorEntity(vehicle, description)
                for vehicle in data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (  # Add energy sites
                TeslemetryEnergySensorEntity(energysite, description)
                for energysite in data.energysites
                for description in ENERGY_DESCRIPTIONS
                if description.key in energysite.coordinator.data
            ),
            (  # Add wall connectors
                TeslemetryWallConnectorSensorEntity(energysite, din, description)
                for energysite in data.energysites
                for din in energysite.coordinator.data.get("wall_connectors", {})
                for description in WALL_CONNECTOR_DESCRIPTIONS
            ),
        )
    )


class TeslemetryVehicleSensorEntity(TeslemetryVehicleEntity, SensorEntity):
    """Base class for Teslemetry vehicle metric sensors."""

    entity_description: TeslemetrySensorEntityDescription

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
        description: TeslemetrySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.get())

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return super().available and self.get() is not None


class TeslemetryEnergySensorEntity(TeslemetryEnergyEntity, SensorEntity):
    """Base class for Teslemetry energy site metric sensors."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        energysite: TeslemetryEnergyData,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(energysite, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.get()


class TeslemetryWallConnectorSensorEntity(TeslemetryWallConnectorEntity, SensorEntity):
    """Base class for Teslemetry energy site metric sensors."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        energysite: TeslemetryEnergyData,
        din: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            energysite,
            din,
            description.key,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._value
