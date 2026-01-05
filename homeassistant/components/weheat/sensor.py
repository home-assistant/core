"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass

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

    value_fn: Callable[[HeatPump], StateType]


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
            lambda status: status.heat_pump_state.name.lower()
            if status.heat_pump_state
            else None
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
        translation_key="energy_output",
        key="energy_output",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_output,
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
        if weheatdata.heat_pump_info.has_dhw:
            entities.extend(
                WeheatHeatPumpSensor(
                    weheatdata.heat_pump_info,
                    weheatdata.data_coordinator,
                    entity_description,
                )
                for entity_description in DHW_SENSORS
                if entity_description.value_fn(weheatdata.data_coordinator.data)
                is not None
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
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
