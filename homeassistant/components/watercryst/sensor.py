"""WATERCryst BIOCAT device sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyocat.models import (
    DeviceResponse,
    MeasurementResponse,
    MlState,
    ModeId,
    StateResponse,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WatercrystConfigEntry
from .entity import WatercrystMeasurementsEntity, WatercrystStateEntity


@dataclass(frozen=True, kw_only=True)
class WatercrystSensorEntityDescription[DataT](SensorEntityDescription):
    """Describes a WATERCryst sensor entity."""

    supported_fn: Callable[[DeviceResponse], bool] = lambda _: True
    value_fn: Callable[[DataT], StateType | datetime]


STATE_SENSORS: list[WatercrystSensorEntityDescription[StateResponse]] = [
    WatercrystSensorEntityDescription[StateResponse](
        key="mode.id",
        translation_key="mode_id",
        device_class=SensorDeviceClass.ENUM,
        options=[mode.value for mode in ModeId],
        value_fn=lambda data: (
            data.mode.id.value if data.mode and data.mode.id else None
        ),
    ),
    WatercrystSensorEntityDescription[StateResponse](
        key="event.event_id",
        translation_key="event_id",
        value_fn=lambda data: data.event.event_id if data.event else None,
    ),
    WatercrystSensorEntityDescription[StateResponse](
        key="event.category",
        translation_key="event_category",
        device_class=SensorDeviceClass.ENUM,
        options=["error", "warning", "info"],
        value_fn=lambda data: data.event.category if data.event else None,
    ),
    WatercrystSensorEntityDescription[StateResponse](
        key="water_protection.pause_leakage_protection_until_utc",
        translation_key="pause_leakage_protection_until_utc",
        device_class=SensorDeviceClass.TIMESTAMP,
        supported_fn=lambda data: data.has_leakage_protection_system,
        value_fn=lambda data: (
            data.water_protection.pause_leakage_protection_until_utc
            if data.water_protection
            else None
        ),
    ),
    WatercrystSensorEntityDescription[StateResponse](
        key="ml_state",
        translation_key="ml_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in MlState],
        supported_fn=lambda data: data.has_leakage_protection_system,
        value_fn=lambda data: data.ml_state.value if data.ml_state else None,
    ),
]

MEASUREMENT_SENSORS: list[WatercrystSensorEntityDescription[MeasurementResponse]] = [
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="water_temp",
        translation_key="water_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        supported_fn=lambda data: data.has_temperature_sensor,
        value_fn=lambda data: data.water_temp,
    ),
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=2,
        supported_fn=lambda data: data.has_pressure_sensor,
        value_fn=lambda data: data.pressure,
    ),
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=2,
        supported_fn=lambda data: data.has_flow_rate_sensor,
        value_fn=lambda data: data.flow_rate,
    ),
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="todays_consumption",
        translation_key="todays_consumption",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
        supported_fn=lambda data: data.has_flow_rate_sensor,
        value_fn=lambda data: data.todays_consumption,
    ),
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="total_consumption",
        translation_key="total_consumption",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
        supported_fn=lambda data: data.has_flow_rate_sensor,
        value_fn=lambda data: data.total_consumption,
    ),
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="last_water_tap_volume",
        translation_key="last_water_tap_volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
        supported_fn=lambda data: data.has_flow_rate_sensor,
        value_fn=lambda data: data.last_water_tap_volume,
    ),
    WatercrystSensorEntityDescription[MeasurementResponse](
        key="last_water_tap_duration",
        translation_key="last_water_tap_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        supported_fn=lambda data: data.has_flow_rate_sensor,
        value_fn=lambda data: data.last_water_tap_duration,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WatercrystConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                WatercrystStateSensor(entry, coordinator, description)
                for description in STATE_SENSORS
                if description.supported_fn(coordinator.data)
            ),
            *(
                WatercrystMeasurementsSensor(entry, coordinator, description)
                for description in MEASUREMENT_SENSORS
                if description.supported_fn(coordinator.data)
            ),
        ]
    )


class WatercrystStateSensor(SensorEntity, WatercrystStateEntity):
    """BIOCAT device state sensor."""

    entity_description: WatercrystSensorEntityDescription[StateResponse]

    @override
    @property
    def native_value(self) -> StateType | datetime:
        if (data := self.coordinator.data) is None:
            return None
        return self.entity_description.value_fn(data)


class WatercrystMeasurementsSensor(SensorEntity, WatercrystMeasurementsEntity):
    """BIOCAT device measurements sensor."""

    entity_description: WatercrystSensorEntityDescription[MeasurementResponse]

    @override
    @property
    def native_value(self) -> StateType | datetime:
        if (data := self.coordinator.data) is None:
            return None
        return self.entity_description.value_fn(data)
