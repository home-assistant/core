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
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WeheatConfigEntry
from .const import (
    DISPLAY_PRECISION_COP,
    DISPLAY_PRECISION_WATER_TEMP,
    DISPLAY_PRECISION_WATTS,
)
from .coordinator import WeheatDataUpdateCoordinator
from .entity import WeheatEntity


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
        translation_key="electricity_used",
        key="electricity_used",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_total,
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
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeheatConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors for weheat heat pump."""
    entities = [
        WeheatHeatPumpSensor(coordinator, entity_description)
        for entity_description in SENSORS
        for coordinator in entry.runtime_data
    ]
    entities.extend(
        WeheatHeatPumpSensor(coordinator, entity_description)
        for entity_description in DHW_SENSORS
        for coordinator in entry.runtime_data
        if coordinator.heat_pump_info.has_dhw
    )

    async_add_entities(entities)


class WeheatHeatPumpSensor(WeheatEntity, SensorEntity):
    """Defines a Weheat heat pump sensor."""

    coordinator: WeheatDataUpdateCoordinator
    entity_description: WeHeatSensorEntityDescription

    def __init__(
        self,
        coordinator: WeheatDataUpdateCoordinator,
        entity_description: WeHeatSensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = f"{coordinator.heatpump_id}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
