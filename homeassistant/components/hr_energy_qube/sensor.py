"""Sensor platform for Qube Heat Pump."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from python_qube_heatpump.models import QubeState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.typing import StateType

from .entity import QubeEntity

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .coordinator import QubeCoordinator

# Status code to state mapping
STATUS_MAP: dict[int, str] = {
    1: "standby",
    2: "alarm",
    6: "keyboard_off",
    8: "compressor_startup",
    9: "compressor_shutdown",
    14: "standby",
    15: "cooling",
    16: "heating",
    17: "start_fail",
    18: "standby",
    22: "heating_dhw",
}


@dataclass(frozen=True, kw_only=True)
class QubeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for Qube Heat Pump."""

    value_fn: Callable[[QubeState], StateType]


def _status_value(data: QubeState) -> StateType:
    """Return status string from status code."""
    code = data.status_code
    if code is None:
        return None
    return STATUS_MAP.get(code)


SENSOR_TYPES: tuple[QubeSensorEntityDescription, ...] = (
    QubeSensorEntityDescription(
        key="temp_supply",
        translation_key="temp_supply",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_supply,
    ),
    QubeSensorEntityDescription(
        key="temp_return",
        translation_key="temp_return",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_return,
    ),
    QubeSensorEntityDescription(
        key="temp_source_in",
        translation_key="temp_source_in",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_source_in,
    ),
    QubeSensorEntityDescription(
        key="temp_source_out",
        translation_key="temp_source_out",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_source_out,
    ),
    QubeSensorEntityDescription(
        key="temp_room",
        translation_key="temp_room",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_room,
    ),
    QubeSensorEntityDescription(
        key="temp_dhw",
        translation_key="temp_dhw",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_dhw,
    ),
    QubeSensorEntityDescription(
        key="temp_outside",
        translation_key="temp_outside",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temp_outside,
    ),
    QubeSensorEntityDescription(
        key="power_thermic",
        translation_key="power_thermic",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.power_thermic,
    ),
    QubeSensorEntityDescription(
        key="power_electric",
        translation_key="power_electric",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.power_electric,
    ),
    QubeSensorEntityDescription(
        key="energy_total_electric",
        translation_key="energy_total_electric",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda data: data.energy_total_electric,
    ),
    QubeSensorEntityDescription(
        key="energy_total_thermic",
        translation_key="energy_total_thermic",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda data: data.energy_total_thermic,
    ),
    QubeSensorEntityDescription(
        key="cop_calc",
        translation_key="cop_calc",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.cop_calc,
    ),
    QubeSensorEntityDescription(
        key="compressor_speed",
        translation_key="compressor_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.compressor_speed,
    ),
    QubeSensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.flow_rate,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_heat_day",
        translation_key="setpoint_room_heat_day",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.setpoint_room_heat_day,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_heat_night",
        translation_key="setpoint_room_heat_night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.setpoint_room_heat_night,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_cool_day",
        translation_key="setpoint_room_cool_day",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.setpoint_room_cool_day,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_cool_night",
        translation_key="setpoint_room_cool_night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.setpoint_room_cool_night,
    ),
    QubeSensorEntityDescription(
        key="status_heatpump",
        translation_key="status_heatpump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "standby",
            "alarm",
            "keyboard_off",
            "compressor_startup",
            "compressor_shutdown",
            "cooling",
            "heating",
            "start_fail",
            "heating_dhw",
        ],
        value_fn=_status_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube sensors."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        QubeSensor(coordinator, entry, description) for description in SENSOR_TYPES
    )


class QubeSensor(QubeEntity, SensorEntity):
    """Qube sensor entity."""

    entity_description: QubeSensorEntityDescription

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
        description: QubeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return native value."""
        return self.entity_description.value_fn(self.coordinator.data)
