"""Sensor platform for NRGkick."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import NRGkickConfigEntry, NRGkickDataUpdateCoordinator, NRGkickEntity
from .const import (
    CELLULAR_MODE_MAP,
    CONNECTOR_TYPE_MAP,
    ERROR_CODE_MAP,
    GRID_PHASES_MAP,
    RCD_TRIGGER_MAP,
    RELAY_STATE_MAP,
    STATUS_MAP,
    WARNING_CODE_MAP,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick sensors based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    entities: list[NRGkickSensor] = [
        # INFO - General
        NRGkickSensor(
            coordinator,
            key="rated_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "general", "rated_current"],
            precision=2,
        ),
        # INFO - Connector
        NRGkickSensor(
            coordinator,
            key="connector_phase_count",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "connector", "phase_count"],
        ),
        NRGkickSensor(
            coordinator,
            key="connector_max_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "connector", "max_current"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="connector_type",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "connector", "type"],
            value_fn=lambda x: (
                CONNECTOR_TYPE_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower()
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="connector_serial",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "connector", "serial"],
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        # INFO - Grid
        NRGkickSensor(
            coordinator,
            key="grid_voltage",
            unit=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "grid", "voltage"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="grid_frequency",
            unit=UnitOfFrequency.HERTZ,
            device_class=SensorDeviceClass.FREQUENCY,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "grid", "frequency"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="grid_phases",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "grid", "phases"],
            value_fn=lambda x: (
                GRID_PHASES_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower().replace(", ", "_").replace(" ", "_")
            ),
        ),
        # INFO - Network
        NRGkickSensor(
            coordinator,
            key="network_ip_address",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "network", "ip_address"],
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="network_mac_address",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "network", "mac_address"],
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="network_ssid",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "network", "ssid"],
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="network_rssi",
            unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "network", "rssi"],
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        # INFO - Cellular (optional, only if cellular module is available)
        NRGkickSensor(
            coordinator,
            key="cellular_mode",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "cellular", "mode"],
            value_fn=lambda x: (
                CELLULAR_MODE_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower()
            ),
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="cellular_rssi",
            unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "cellular", "rssi"],
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="cellular_operator",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "cellular", "operator"],
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        # INFO - GPS (optional, only if GPS module is available)
        NRGkickSensor(
            coordinator,
            key="gps_latitude",
            unit="°",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "gps", "latitude"],
            precision=6,
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="gps_longitude",
            unit="°",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "gps", "longitude"],
            precision=6,
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="gps_altitude",
            unit="m",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "gps", "altitude"],
            precision=2,
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="gps_accuracy",
            unit="m",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["info", "gps", "accuracy"],
            precision=2,
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        # INFO - Versions
        NRGkickSensor(
            coordinator,
            key="versions_sw_sm",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "versions", "sw_sm"],
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="versions_hw_sm",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["info", "versions", "hw_sm"],
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        # Control
        NRGkickSensor(
            coordinator,
            key="current_set",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["control", "current_set"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="charge_pause",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["control", "charge_pause"],
        ),
        NRGkickSensor(
            coordinator,
            key="energy_limit",
            unit=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            value_path=["control", "energy_limit"],
            precision=3,
            suggested_unit=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        NRGkickSensor(
            coordinator,
            key="phase_count",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["control", "phase_count"],
        ),
        # VALUES - Energy
        NRGkickSensor(
            coordinator,
            key="total_charged_energy",
            unit=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_path=["values", "energy", "total_charged_energy"],
            precision=3,
            suggested_unit=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        NRGkickSensor(
            coordinator,
            key="charged_energy",
            unit=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_path=["values", "energy", "charged_energy"],
            precision=3,
            suggested_unit=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        # VALUES - Powerflow (Total)
        NRGkickSensor(
            coordinator,
            key="charging_voltage",
            unit=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "charging_voltage"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="charging_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "charging_current"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="powerflow_grid_frequency",
            unit=UnitOfFrequency.HERTZ,
            device_class=SensorDeviceClass.FREQUENCY,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "grid_frequency"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="peak_power",
            unit=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "peak_power"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="total_active_power",
            unit=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "total_active_power"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="total_reactive_power",
            unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "total_reactive_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="total_apparent_power",
            unit=UnitOfApparentPower.VOLT_AMPERE,
            device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "total_apparent_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="total_power_factor",
            unit=PERCENTAGE,
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "total_power_factor"],
        ),
        # VALUES - Powerflow L1
        NRGkickSensor(
            coordinator,
            key="l1_voltage",
            unit=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l1", "voltage"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l1_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l1", "current"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l1_active_power",
            unit=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l1", "active_power"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l1_reactive_power",
            unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l1", "reactive_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="l1_apparent_power",
            unit=UnitOfApparentPower.VOLT_AMPERE,
            device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l1", "apparent_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="l1_power_factor",
            unit=PERCENTAGE,
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l1", "power_factor"],
        ),
        # VALUES - Powerflow L2
        NRGkickSensor(
            coordinator,
            key="l2_voltage",
            unit=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l2", "voltage"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l2_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l2", "current"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l2_active_power",
            unit=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l2", "active_power"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l2_reactive_power",
            unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l2", "reactive_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="l2_apparent_power",
            unit=UnitOfApparentPower.VOLT_AMPERE,
            device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l2", "apparent_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="l2_power_factor",
            unit=PERCENTAGE,
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l2", "power_factor"],
        ),
        # VALUES - Powerflow L3
        NRGkickSensor(
            coordinator,
            key="l3_voltage",
            unit=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l3", "voltage"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l3_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l3", "current"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l3_active_power",
            unit=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l3", "active_power"],
            precision=2,
        ),
        NRGkickSensor(
            coordinator,
            key="l3_reactive_power",
            unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l3", "reactive_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="l3_apparent_power",
            unit=UnitOfApparentPower.VOLT_AMPERE,
            device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l3", "apparent_power"],
        ),
        NRGkickSensor(
            coordinator,
            key="l3_power_factor",
            unit=PERCENTAGE,
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "l3", "power_factor"],
        ),
        # VALUES - Powerflow Neutral
        NRGkickSensor(
            coordinator,
            key="n_current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "powerflow", "n", "current"],
            precision=2,
        ),
        # VALUES - General
        NRGkickSensor(
            coordinator,
            key="charging_rate",
            unit=None,
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "general", "charging_rate"],
        ),
        NRGkickSensor(
            coordinator,
            key="vehicle_connect_time",
            unit=UnitOfTime.SECONDS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "general", "vehicle_connect_time"],
        ),
        NRGkickSensor(
            coordinator,
            key="vehicle_charging_time",
            unit=UnitOfTime.SECONDS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "general", "vehicle_charging_time"],
        ),
        NRGkickSensor(
            coordinator,
            key="status",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["values", "general", "status"],
            value_fn=lambda x: (
                STATUS_MAP.get(x, "unknown") if isinstance(x, int) else str(x).lower()
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="charge_permitted",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["values", "general", "charge_permitted"],
        ),
        NRGkickSensor(
            coordinator,
            key="relay_state",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["values", "general", "relay_state"],
            value_fn=lambda x: (
                RELAY_STATE_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower().replace(", ", "_").replace(" ", "_")
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="charge_count",
            unit=None,
            device_class=None,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_path=["values", "general", "charge_count"],
        ),
        NRGkickSensor(
            coordinator,
            key="rcd_trigger",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["values", "general", "rcd_trigger"],
            value_fn=lambda x: (
                RCD_TRIGGER_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower()
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="warning_code",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["values", "general", "warning_code"],
            value_fn=lambda x: (
                WARNING_CODE_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower()
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        NRGkickSensor(
            coordinator,
            key="error_code",
            unit=None,
            device_class=None,
            state_class=None,
            value_path=["values", "general", "error_code"],
            value_fn=lambda x: (
                ERROR_CODE_MAP.get(x, "unknown")
                if isinstance(x, int)
                else str(x).lower()
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        # VALUES - Temperatures
        NRGkickSensor(
            coordinator,
            key="housing_temperature",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "temperatures", "housing"],
        ),
        NRGkickSensor(
            coordinator,
            key="connector_l1_temperature",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "temperatures", "connector_l1"],
        ),
        NRGkickSensor(
            coordinator,
            key="connector_l2_temperature",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "temperatures", "connector_l2"],
        ),
        NRGkickSensor(
            coordinator,
            key="connector_l3_temperature",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "temperatures", "connector_l3"],
        ),
        NRGkickSensor(
            coordinator,
            key="domestic_plug_1_temperature",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "temperatures", "domestic_plug_1"],
        ),
        NRGkickSensor(
            coordinator,
            key="domestic_plug_2_temperature",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_path=["values", "temperatures", "domestic_plug_2"],
        ),
    ]

    async_add_entities(entities)


class NRGkickSensor(NRGkickEntity, SensorEntity):
    """Representation of a NRGkick sensor."""

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        *,
        key: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        value_path: list[str],
        entity_category: EntityCategory | None = None,
        value_fn: Callable[[Any], Any] | None = None,
        precision: int | None = None,
        suggested_unit: str | None = None,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._value_path = value_path
        self._attr_entity_category = entity_category
        self._value_fn = value_fn
        self._attr_entity_registry_enabled_default = enabled_default

        if precision is not None:
            self._attr_suggested_display_precision = precision
        if suggested_unit is not None:
            self._attr_suggested_unit_of_measurement = suggested_unit

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data: Any = self.coordinator.data
        for key in self._value_path:
            if data is None:
                return None
            data = data.get(key)

        if self._value_fn and data is not None:
            return cast(StateType, self._value_fn(data))
        return cast(StateType, data)
