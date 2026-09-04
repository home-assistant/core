"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import override

from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DISPLAY_PRECISION_COP,
    DISPLAY_PRECISION_FLOW,
    DISPLAY_PRECISION_WATER_TEMP,
    DISPLAY_PRECISION_WATTS,
)
from .coordinator import (
    HeatPumpInfo,
    WeheatConfigEntry,
    WeheatDataUpdateCoordinator,
    WeheatEnergyUpdateCoordinator,
)
from .entity import WeheatEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WeHeatSensorEntityDescription(SensorEntityDescription):
    """Describes Weheat sensor entity."""

    value_fn: Callable[[HeatPump], StateType | datetime]


# The portal counts the conditions the heat pump waits on and leaves these two
# settings out of its tally.
COOLING_CONDITIONS_NOT_COUNTED = ("control_method", "contact_not_blocked")


def _cooling_wait_until(status: HeatPump) -> datetime | None:
    """Return when the wait after the last cooling cycle runs out."""
    conditions = status.cooling_start_conditions
    if conditions is None or conditions["exponential_backoff"]:
        return None
    return status.cooling_available_from


# A cooling state is only reported during a cooling cycle and covers every substate
# of it, including the water check the overall heat pump state reports as its own.
def _cooling_conditions_met(status: HeatPump) -> int | None:
    """Return how many conditions for starting cooling are met, as the portal counts."""
    conditions = status.cooling_start_conditions
    if conditions is None or status.cooling_state is not None:
        return None
    return sum(
        met
        for name, met in conditions.items()
        if name not in COOLING_CONDITIONS_NOT_COUNTED
    )


def _cooling_blocked_by(status: HeatPump) -> str | None:
    """Return the first condition keeping the heat pump from cooling."""
    conditions = status.cooling_start_conditions
    if conditions is None:
        return None
    if status.cooling_state is not None:
        return "none"
    return next((name for name, met in conditions.items() if not met), "none")


def _latched_reason(status: HeatPump, reason: Enum | None) -> str | None:
    """Return a reason from before the cycle, which says nothing while one runs."""
    if status.cooling_state is not None:
        return "none"
    return reason.name.lower() if reason is not None else None


SENSORS = [
    WeHeatSensorEntityDescription(
        translation_key="power_output",
        key="power_output",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATTS,
        value_fn=lambda status: status.power_output,
    ),
    WeHeatSensorEntityDescription(
        translation_key="power_input",
        key="power_input",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATTS,
        value_fn=lambda status: status.power_input,
    ),
    WeHeatSensorEntityDescription(
        translation_key="cop",
        key="cop",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_COP,
        value_fn=lambda status: status.cop,
    ),
    WeHeatSensorEntityDescription(
        translation_key="water_inlet_temperature",
        key="water_inlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.water_inlet_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="water_outlet_temperature",
        key="water_outlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.water_outlet_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="ch_inlet_temperature",
        key="ch_inlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.water_house_in_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="outside_temperature",
        key="outside_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.air_inlet_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="air_outlet_temperature",
        key="air_outlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.air_outlet_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="thermostat_water_setpoint",
        key="thermostat_water_setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.thermostat_water_setpoint,
    ),
    WeHeatSensorEntityDescription(
        translation_key="thermostat_room_temperature",
        key="thermostat_room_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.thermostat_room_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="thermostat_room_temperature_setpoint",
        key="thermostat_room_temperature_setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.thermostat_room_temperature_setpoint,
    ),
    WeHeatSensorEntityDescription(
        translation_key="heat_pump_state",
        key="heat_pump_state",
        name=None,
        device_class=SensorDeviceClass.ENUM,
        options=[s.name.lower() for s in HeatPump.State],
        value_fn=(
            lambda status: (
                status.heat_pump_state.name.lower() if status.heat_pump_state else None
            )
        ),
    ),
    WeHeatSensorEntityDescription(
        translation_key="compressor_rpm",
        key="compressor_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda status: status.compressor_rpm,
    ),
    WeHeatSensorEntityDescription(
        translation_key="compressor_percentage",
        key="compressor_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda status: status.compressor_percentage,
    ),
    WeHeatSensorEntityDescription(
        translation_key="central_heating_flow_volume",
        key="central_heating_flow_volume",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_FLOW,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        value_fn=lambda status: status.central_heating_flow_volume,
    ),
]

DHW_SENSORS = [
    WeHeatSensorEntityDescription(
        translation_key="dhw_top_temperature",
        key="dhw_top_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.dhw_top_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="dhw_bottom_temperature",
        key="dhw_bottom_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        value_fn=lambda status: status.dhw_bottom_temperature,
    ),
    WeHeatSensorEntityDescription(
        translation_key="dhw_flow_volume",
        key="dhw_flow_volume",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_FLOW,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        value_fn=lambda status: status.dhw_flow_volume,
    ),
    WeHeatSensorEntityDescription(
        translation_key="dhw_target_temperature",
        key="dhw_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATER_TEMP,
        # A target of zero is how the heat pump says DHW control is off.
        value_fn=lambda status: status.dhw_target_temperature or None,
    ),
    WeHeatSensorEntityDescription(
        translation_key="dhw_control_method",
        key="dhw_control_method",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[method.name.lower() for method in HeatPump.DhwControlMethod],
        value_fn=(
            lambda status: (
                status.dhw_control_method.name.lower()
                if status.dhw_control_method is not None
                else None
            )
        ),
    ),
]

COOLING_SENSORS = [
    WeHeatSensorEntityDescription(
        translation_key="cooling_state",
        key="cooling_state",
        device_class=SensorDeviceClass.ENUM,
        options=[activity.name.lower() for activity in HeatPump.CoolingActivity],
        value_fn=lambda status: (
            status.cooling_activity.name.lower()
            if status.cooling_activity is not None
            else None
        ),
    ),
    WeHeatSensorEntityDescription(
        translation_key="cooling_blocked_by",
        key="cooling_blocked_by",
        device_class=SensorDeviceClass.ENUM,
        options=["none", *HeatPump.COOLING_START_CONDITION_BITS],
        value_fn=_cooling_blocked_by,
    ),
    WeHeatSensorEntityDescription(
        translation_key="cooling_conditions_met",
        key="cooling_conditions_met",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_cooling_conditions_met,
    ),
    WeHeatSensorEntityDescription(
        translation_key="cooling_wait_until",
        key="cooling_wait_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_cooling_wait_until,
    ),
    WeHeatSensorEntityDescription(
        translation_key="last_cooling_time",
        key="last_cooling_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda status: status.last_cooling_time,
    ),
    WeHeatSensorEntityDescription(
        translation_key="cooling_pause_reason",
        key="cooling_pause_reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[reason.name.lower() for reason in HeatPump.CoolingPauseReason],
        value_fn=lambda status: _latched_reason(status, status.cooling_pause_reason),
    ),
    WeHeatSensorEntityDescription(
        translation_key="cooling_stop_reason",
        key="cooling_stop_reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[reason.name.lower() for reason in HeatPump.CoolingStopReason],
        value_fn=lambda status: _latched_reason(status, status.cooling_stop_reason),
    ),
]


ENERGY_SENSORS = [
    WeHeatSensorEntityDescription(
        translation_key="electricity_used",
        key="electricity_used",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_total,
    ),
    WeHeatSensorEntityDescription(
        translation_key="electricity_used_indoor_unit",
        key="electricity_used_indoor_unit",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_in_indoor_unit,
    ),
    WeHeatSensorEntityDescription(
        translation_key="energy_output",
        key="energy_output",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.energy_output,
    ),
    WeHeatSensorEntityDescription(
        translation_key="electricity_used_heating",
        key="electricity_used_heating",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_in_heating,
    ),
    WeHeatSensorEntityDescription(
        translation_key="electricity_used_cooling",
        key="electricity_used_cooling",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_in_cooling,
    ),
    WeHeatSensorEntityDescription(
        translation_key="electricity_used_defrost",
        key="electricity_used_defrost",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_in_defrost,
    ),
    WeHeatSensorEntityDescription(
        translation_key="electricity_used_standby",
        key="electricity_used_standby",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_in_standby,
    ),
    WeHeatSensorEntityDescription(
        translation_key="energy_output_heating",
        key="energy_output_heating",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_out_heating,
    ),
    WeHeatSensorEntityDescription(
        translation_key="energy_output_cooling",
        key="energy_output_cooling",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.energy_out_cooling,
    ),
    WeHeatSensorEntityDescription(
        translation_key="energy_output_defrost",
        key="energy_output_defrost",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.energy_out_defrost,
    ),
]

DHW_ENERGY_SENSORS = [
    WeHeatSensorEntityDescription(
        translation_key="electricity_used_dhw",
        key="electricity_used_dhw",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_in_dhw,
    ),
    WeHeatSensorEntityDescription(
        translation_key="energy_output_dhw",
        key="energy_output_dhw",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_out_dhw,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeheatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for weheat heat pump."""

    entities: list[WeheatHeatPumpSensor] = []
    for weheatdata in entry.runtime_data:
        entities.extend(
            WeheatHeatPumpSensor(
                weheatdata.heat_pump_info,
                weheatdata.data_coordinator,
                entity_description,
            )
            for entity_description in SENSORS
            if entity_description.value_fn(weheatdata.data_coordinator.data) is not None
        )
        if weheatdata.data_coordinator.data.cooling_activity is not None:
            entities.extend(
                WeheatHeatPumpSensor(
                    weheatdata.heat_pump_info,
                    weheatdata.data_coordinator,
                    entity_description,
                )
                for entity_description in COOLING_SENSORS
            )
        if weheatdata.heat_pump_info.has_dhw:
            entities.extend(
                WeheatHeatPumpSensor(
                    weheatdata.heat_pump_info,
                    weheatdata.data_coordinator,
                    entity_description,
                )
                for entity_description in DHW_SENSORS
            )
            entities.extend(
                WeheatHeatPumpSensor(
                    weheatdata.heat_pump_info,
                    weheatdata.energy_coordinator,
                    entity_description,
                )
                for entity_description in DHW_ENERGY_SENSORS
            )
        entities.extend(
            WeheatHeatPumpSensor(
                weheatdata.heat_pump_info,
                weheatdata.energy_coordinator,
                entity_description,
            )
            for entity_description in ENERGY_SENSORS
            if entity_description.value_fn(weheatdata.energy_coordinator.data)
            is not None
        )

    async_add_entities(entities)


class WeheatHeatPumpSensor(WeheatEntity, SensorEntity):
    """Defines a Weheat heat pump sensor."""

    heat_pump_info: HeatPumpInfo
    coordinator: WeheatDataUpdateCoordinator | WeheatEnergyUpdateCoordinator
    entity_description: WeHeatSensorEntityDescription

    def __init__(
        self,
        heat_pump_info: HeatPumpInfo,
        coordinator: WeheatDataUpdateCoordinator | WeheatEnergyUpdateCoordinator,
        entity_description: WeHeatSensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(heat_pump_info, coordinator)
        self.entity_description = entity_description

        self._attr_unique_id = f"{heat_pump_info.heatpump_id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
