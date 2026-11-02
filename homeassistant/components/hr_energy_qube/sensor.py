"""Sensor platform for Qube Heat Pump."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from python_qube_heatpump import StatusCode

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

from .coordinator import QubeData
from .entity import QubeEntity

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .coordinator import QubeCoordinator

# The library combines the status code with the anti-legionella request into
# one status; anti-legionella takes precedence over everything except an alarm.
STATUS_OPTIONS: list[str] = [
    status.value for status in StatusCode if status is not StatusCode.UNKNOWN
]


@dataclass(frozen=True, kw_only=True)
class QubeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for Qube Heat Pump."""

    value_fn: Callable[[QubeData], StateType]


def _status_value(data: QubeData) -> StateType:
    """Return the heat pump status."""
    status = data.state.status
    if status is None or status is StatusCode.UNKNOWN:
        return None
    return str(status.value)


SENSOR_TYPES: tuple[QubeSensorEntityDescription, ...] = (
    QubeSensorEntityDescription(
        key="temp_supply",
        translation_key="temp_supply",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_supply,
    ),
    QubeSensorEntityDescription(
        key="temp_return",
        translation_key="temp_return",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_return,
    ),
    QubeSensorEntityDescription(
        key="temp_source_in",
        translation_key="temp_source_in",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_source_in,
    ),
    QubeSensorEntityDescription(
        key="temp_source_out",
        translation_key="temp_source_out",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_source_out,
    ),
    QubeSensorEntityDescription(
        key="temp_room",
        translation_key="temp_room",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_room,
    ),
    QubeSensorEntityDescription(
        key="temp_dhw",
        translation_key="temp_dhw",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_dhw,
    ),
    QubeSensorEntityDescription(
        key="temp_outside",
        translation_key="temp_outside",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.temp_outside,
    ),
    QubeSensorEntityDescription(
        key="power_thermic",
        translation_key="power_thermic",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.state.power_thermic,
    ),
    QubeSensorEntityDescription(
        key="power_electric",
        translation_key="power_electric",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.state.power_electric,
    ),
    QubeSensorEntityDescription(
        key="energy_total_electric",
        translation_key="energy_total_electric",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda data: data.state.energy_total_electric,
    ),
    QubeSensorEntityDescription(
        key="energy_total_thermic",
        translation_key="energy_total_thermic",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda data: data.state.energy_total_thermic,
    ),
    QubeSensorEntityDescription(
        key="cop_calc",
        translation_key="cop_calc",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.cop_calc,
    ),
    QubeSensorEntityDescription(
        key="compressor_speed",
        translation_key="compressor_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.state.compressor_speed,
    ),
    QubeSensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.state.flow_rate,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_heat_day",
        translation_key="setpoint_room_heat_day",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.setpoint_room_heat_day,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_heat_night",
        translation_key="setpoint_room_heat_night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.setpoint_room_heat_night,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_cool_day",
        translation_key="setpoint_room_cool_day",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.setpoint_room_cool_day,
    ),
    QubeSensorEntityDescription(
        key="setpoint_room_cool_night",
        translation_key="setpoint_room_cool_night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.setpoint_room_cool_night,
    ),
    QubeSensorEntityDescription(
        key="status_heatpump",
        translation_key="status_heatpump",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        value_fn=_status_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube sensors."""
    coordinator = entry.runtime_data

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
    @override
    def native_value(self) -> StateType:
        """Return native value."""
        return self.entity_description.value_fn(self.coordinator.data)
