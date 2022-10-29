"""Sensor platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, SensiboMotionBaseEntity

PARALLEL_UPDATES = 0


@dataclass
class MotionBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[MotionSensor], StateType]


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[SensiboDevice], StateType | datetime]
    extra_fn: Callable[[SensiboDevice], dict[str, str | bool | None] | None] | None


@dataclass
class SensiboMotionSensorEntityDescription(
    SensorEntityDescription, MotionBaseEntityDescriptionMixin
):
    """Describes Sensibo Motion sensor entity."""


@dataclass
class SensiboDeviceSensorEntityDescription(
    SensorEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Sensibo Device sensor entity."""


FILTER_LAST_RESET_DESCRIPTION = SensiboDeviceSensorEntityDescription(
    key="filter_last_reset",
    device_class=SensorDeviceClass.TIMESTAMP,
    name="Filter last reset",
    icon="mdi:timer",
    value_fn=lambda data: data.filter_last_reset,
    extra_fn=None,
)

MOTION_SENSOR_TYPES: tuple[SensiboMotionSensorEntityDescription, ...] = (
    SensiboMotionSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        name="rssi",
        icon="mdi:wifi",
        value_fn=lambda data: data.rssi,
        entity_registry_enabled_default=False,
    ),
    SensiboMotionSensorEntityDescription(
        key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        name="Battery voltage",
        icon="mdi:battery",
        value_fn=lambda data: data.battery_voltage,
    ),
    SensiboMotionSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Humidity",
        icon="mdi:water",
        value_fn=lambda data: data.humidity,
    ),
    SensiboMotionSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Temperature",
        icon="mdi:thermometer",
        value_fn=lambda data: data.temperature,
    ),
)
PURE_SENSOR_TYPES: tuple[SensiboDeviceSensorEntityDescription, ...] = (
    SensiboDeviceSensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        name="PM2.5",
        icon="mdi:air-filter",
        value_fn=lambda data: data.pm25,
        extra_fn=None,
    ),
    SensiboDeviceSensorEntityDescription(
        key="pure_sensitivity",
        name="Pure sensitivity",
        icon="mdi:air-filter",
        value_fn=lambda data: data.pure_sensitivity,
        extra_fn=None,
        device_class="sensibo__sensitivity",
    ),
    FILTER_LAST_RESET_DESCRIPTION,
)

DEVICE_SENSOR_TYPES: tuple[SensiboDeviceSensorEntityDescription, ...] = (
    SensiboDeviceSensorEntityDescription(
        key="timer_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Timer end time",
        icon="mdi:timer",
        value_fn=lambda data: data.timer_time,
        extra_fn=lambda data: {"id": data.timer_id, "turn_on": data.timer_state_on},
    ),
    SensiboDeviceSensorEntityDescription(
        key="feels_like",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Temperature feels like",
        value_fn=lambda data: data.feelslike,
        extra_fn=None,
        entity_registry_enabled_default=False,
    ),
    SensiboDeviceSensorEntityDescription(
        key="climate_react_low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Climate React low temperature threshold",
        value_fn=lambda data: data.smart_low_temp_threshold,
        extra_fn=lambda data: data.smart_low_state,
        entity_registry_enabled_default=False,
    ),
    SensiboDeviceSensorEntityDescription(
        key="climate_react_high",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Climate React high temperature threshold",
        value_fn=lambda data: data.smart_high_temp_threshold,
        extra_fn=lambda data: data.smart_high_state,
        entity_registry_enabled_default=False,
    ),
    SensiboDeviceSensorEntityDescription(
        key="climate_react_type",
        device_class="sensibo__smart_type",
        name="Climate React type",
        value_fn=lambda data: data.smart_type,
        extra_fn=None,
        entity_registry_enabled_default=False,
    ),
    FILTER_LAST_RESET_DESCRIPTION,
)

AIRQ_SENSOR_TYPES: tuple[SensiboDeviceSensorEntityDescription, ...] = (
    SensiboDeviceSensorEntityDescription(
        key="airq_tvoc",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
        name="AirQ TVOC",
        value_fn=lambda data: data.tvoc,
        extra_fn=None,
    ),
    SensiboDeviceSensorEntityDescription(
        key="airq_co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        name="AirQ CO2",
        value_fn=lambda data: data.co2,
        extra_fn=None,
    ),
)

DESCRIPTION_BY_MODELS = {"pure": PURE_SENSOR_TYPES, "airq": AIRQ_SENSOR_TYPES}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboMotionSensor | SensiboDeviceSensor] = []

    for device_id, device_data in coordinator.data.parsed.items():
        if device_data.motion_sensors:
            entities.extend(
                SensiboMotionSensor(
                    coordinator, device_id, sensor_id, sensor_data, description
                )
                for sensor_id, sensor_data in device_data.motion_sensors.items()
                for description in MOTION_SENSOR_TYPES
            )
    entities.extend(
        SensiboDeviceSensor(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in DESCRIPTION_BY_MODELS.get(
            device_data.model, DEVICE_SENSOR_TYPES
        )
    )
    async_add_entities(entities)


class SensiboMotionSensor(SensiboMotionBaseEntity, SensorEntity):
    """Representation of a Sensibo Motion Sensor."""

    entity_description: SensiboMotionSensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
        entity_description: SensiboMotionSensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Motion Sensor."""
        super().__init__(
            coordinator,
            device_id,
            sensor_id,
            sensor_data,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{sensor_id}-{entity_description.key}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Add native unit of measurement."""
        if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
            return TEMP_CELSIUS
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if TYPE_CHECKING:
            assert self.sensor_data
        return self.entity_description.value_fn(self.sensor_data)


class SensiboDeviceSensor(SensiboDeviceBaseEntity, SensorEntity):
    """Representation of a Sensibo Device Sensor."""

    entity_description: SensiboDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboDeviceSensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Sensor."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Add native unit of measurement."""
        if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
            return TEMP_CELSIUS
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> StateType | datetime:
        """Return value of sensor."""
        state = self.entity_description.value_fn(self.device_data)
        if isinstance(state, str):
            return state.lower()
        return state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.extra_fn is not None:
            return self.entity_description.extra_fn(self.device_data)
        return None
