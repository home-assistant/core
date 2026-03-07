"""Sensor platform for Nest."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.models import (
    NestCamera,
    NestDevice,
    NestHeatLink,
    NestLock,
    NestProtect,
    NestTempSensor,
    NestThermostat,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NestSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Nest sensor."""

    value_fn: Callable[[Any], StateType | datetime.datetime]
    device_types: tuple[type[NestDevice], ...]


_DESCRIPTIONS: tuple[NestSensorEntityDescription, ...] = (
    NestSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        value_fn=lambda device: device.battery_voltage,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_types=(
            NestProtect,
            NestTempSensor,
            NestLock,
            NestCamera,
            NestThermostat,
        ),
    ),
    NestSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        value_fn=lambda device: (
            round(device.battery_level) if device.battery_level is not None else None
        ),
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_types=(
            NestProtect,
            NestTempSensor,
            NestLock,
            NestCamera,
            NestThermostat,
        ),
    ),
    # Protect
    NestSensorEntityDescription(
        key="replace_by_date",
        translation_key="replace_by",
        value_fn=lambda device: device.replace_by_date,
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestProtect,),
    ),
    NestSensorEntityDescription(
        key="latest_manual_test_end_utc_secs",
        translation_key="last_manual_test",
        value_fn=lambda device: (
            datetime.datetime.fromtimestamp(
                device.latest_manual_test_end_utc_secs, datetime.UTC
            )
            if device.latest_manual_test_end_utc_secs > 0
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestSensorEntityDescription(
        key="last_audio_self_test_end_utc_secs",
        translation_key="last_audio_self_test",
        value_fn=lambda device: (
            datetime.datetime.fromtimestamp(
                device.last_audio_self_test_end_utc_secs, datetime.UTC
            )
            if device.last_audio_self_test_end_utc_secs > 0
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    # Temp Sensor
    NestSensorEntityDescription(
        key="current_temperature",
        translation_key="temperature",
        value_fn=lambda device: device.current_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_types=(NestTempSensor, NestThermostat, NestHeatLink),
    ),
    # Thermostat
    NestSensorEntityDescription(
        key="current_humidity",
        translation_key="humidity",
        value_fn=lambda device: device.current_humidity,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_types=(NestThermostat,),
    ),
    NestSensorEntityDescription(
        key="target_humidity",
        translation_key="target_humidity",
        value_fn=lambda device: device.target_humidity,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestThermostat,),
    ),
    NestSensorEntityDescription(
        key="backplate_temperature",
        translation_key="backplate_temperature",
        value_fn=lambda device: device.backplate_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestThermostat,),
    ),
    NestSensorEntityDescription(
        key="filter_runtime",
        translation_key="filter_runtime",
        value_fn=lambda device: device.filter_runtime,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestThermostat,),
    ),
    # Lock
    NestSensorEntityDescription(
        key="bolt_actor",
        translation_key="last_action",
        icon="mdi:history",
        value_fn=lambda device: device.bolt_actor,
        device_types=(NestLock,),
    ),
)

_FAN_DESCRIPTIONS: tuple[NestSensorEntityDescription, ...] = (
    NestSensorEntityDescription(
        key="fan_duration",
        translation_key="fan_duration_config",
        value_fn=lambda device: device.fan_duration,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestThermostat,),
        entity_registry_enabled_default=False,
    ),
    NestSensorEntityDescription(
        key="fan_timer_timeout",
        translation_key="fan_timer_timeout",
        value_fn=lambda device: (
            datetime.datetime.fromtimestamp(device.fan_timer_timeout, datetime.UTC)
            if device.fan_timer_timeout > 0
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_types=(NestThermostat,),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest sensors from a config entry."""
    coordinator = entry.runtime_data
    entities = [
        NestSensor(coordinator, device, description)
        for device in coordinator.data.values()
        for description in _DESCRIPTIONS
        if isinstance(device, description.device_types)
        and hasattr(device, description.key)
        # Handle optional fields (like target_humidity)
        and getattr(device, description.key) is not None
    ]
    # Add fan-specific sensors
    entities.extend(
        NestSensor(coordinator, device, description)
        for device in coordinator.data.values()
        if isinstance(device, NestThermostat) and device.has_fan
        for description in _FAN_DESCRIPTIONS
        if hasattr(device, description.key)
    )
    async_add_devices(entities)


class NestSensor(NestEntity[NestDevice], SensorEntity):
    """Representation of a Nest Sensor."""

    entity_description: NestSensorEntityDescription

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestDevice,
        description: NestSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.serial_number}-{description.key}"

    @property
    def native_value(self) -> StateType | datetime.datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)
