"""WATERCryst BIOCAT device sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from pyocat.models import MeasurementResponse, StateResponse

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

from . import RuntimeData, WatercrystConfigEntry
from .coordinator import WatercrystDataUpdateCoordinator
from .entity import WatercrystEntity


@dataclass(frozen=True, kw_only=True)
class WatercrystSensorEntityDescription[DataT](SensorEntityDescription):
    """Describes a WATERCryst sensor entity."""

    supported_fn: Callable[[RuntimeData], bool] = lambda _: True
    value_fn: Callable[[DataT], StateType | datetime]


MODES = {
    "ER": "error_mode",
    "FS": "fail_safe",
    "LS": "leakage_protection",
    "MC": "manual_control",
    "RS": "rinse",
    "ST": "self_test",
    "TD": "thermal_disinfection",
    "UD": "update",
    "WO": "water_off",
    "WT": "water_treatment",
}

ML_STATES = {
    "cancelled": "cancelled",
    "failure-pressure-drop": "failure_pressure_drop",
    "failure-start-pressure": "failure_start_pressure",
    "failure-unknown": "failure_unknown",
    "failure-water-tap": "failure_water_tap",
    "idle": "idle",
    "leakage": "leakage",
    "running": "running",
    "success": "success",
}


STATE_SENSORS: list[WatercrystSensorEntityDescription[StateResponse]] = [
    WatercrystSensorEntityDescription[StateResponse](
        key="mode.id",
        translation_key="mode_id",
        device_class=SensorDeviceClass.ENUM,
        options=list(MODES.values()),
        value_fn=lambda data: (
            MODES.get(data.mode.id) if data.mode and data.mode.id else None
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
        options=list(ML_STATES.values()),
        supported_fn=lambda data: data.has_leakage_protection_system,
        value_fn=lambda data: ML_STATES.get(data.ml_state) if data.ml_state else None,
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
    data = entry.runtime_data

    async_add_entities(
        [
            *(
                WatercrystSensor(entry, data.state, description)
                for description in STATE_SENSORS
                if description.supported_fn(data)
            ),
            *(
                WatercrystSensor(entry, data.measurements, description)
                for description in MEASUREMENT_SENSORS
                if description.supported_fn(data)
            ),
        ]
    )


# NOTE: The coordinator is supposed to be WatercrystDataUpdateCoordinator[DataT]
#       but mypy reports an error that DataT is undefined.
class WatercrystSensor[DataT, CoordinatorT: WatercrystDataUpdateCoordinator[Any]](
    SensorEntity, WatercrystEntity[CoordinatorT]
):
    """BIOCAT device sensor base class."""

    entity_description: WatercrystSensorEntityDescription[DataT]

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        await super().async_added_to_hass()

        if self.coordinator is not self._state:
            self.async_on_remove(
                self._state.async_add_listener(self.async_write_ha_state)
            )

    @override
    @property
    def native_value(self) -> StateType | datetime:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
