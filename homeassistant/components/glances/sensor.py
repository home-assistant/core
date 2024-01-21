"""Support gathering system information of hosts which are running glances."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GlancesDataUpdateCoordinator
from .const import CPU_ICON, DOMAIN


@dataclass(frozen=True)
class GlancesSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    type: str


@dataclass(frozen=True)
class GlancesSensorEntityDescription(
    SensorEntityDescription, GlancesSensorEntityDescriptionMixin
):
    """Describe Glances sensor entity."""


SENSOR_TYPES = {
    ("fs", "disk_use_percent"): GlancesSensorEntityDescription(
        key="disk_use_percent",
        type="fs",
        translation_key="disk_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_use"): GlancesSensorEntityDescription(
        key="disk_use",
        type="fs",
        translation_key="disk_used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_free"): GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        translation_key="disk_free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_use_percent"): GlancesSensorEntityDescription(
        key="memory_use_percent",
        type="mem",
        translation_key="memory_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_use"): GlancesSensorEntityDescription(
        key="memory_use",
        type="mem",
        translation_key="memory_used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_free"): GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        translation_key="memory_free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_use_percent"): GlancesSensorEntityDescription(
        key="swap_use_percent",
        type="memswap",
        translation_key="swap_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_use"): GlancesSensorEntityDescription(
        key="swap_use",
        type="memswap",
        translation_key="swap_used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_free"): GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        translation_key="swap_free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("load", "processor_load"): GlancesSensorEntityDescription(
        key="processor_load",
        type="load",
        translation_key="processor_load",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_running"): GlancesSensorEntityDescription(
        key="process_running",
        type="processcount",
        translation_key="process_running",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_total"): GlancesSensorEntityDescription(
        key="process_total",
        type="processcount",
        translation_key="process_total",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_thread"): GlancesSensorEntityDescription(
        key="process_thread",
        type="processcount",
        translation_key="process_threads",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_sleeping"): GlancesSensorEntityDescription(
        key="process_sleeping",
        type="processcount",
        translation_key="process_sleeping",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("cpu", "cpu_use_percent"): GlancesSensorEntityDescription(
        key="cpu_use_percent",
        type="cpu",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "temperature_core"): GlancesSensorEntityDescription(
        key="temperature_core",
        type="sensors",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "temperature_hdd"): GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "fan_speed"): GlancesSensorEntityDescription(
        key="fan_speed",
        type="sensors",
        translation_key="fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "battery"): GlancesSensorEntityDescription(
        key="battery",
        type="sensors",
        translation_key="charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_active"): GlancesSensorEntityDescription(
        key="docker_active",
        type="docker",
        translation_key="container_active",
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_cpu_use"): GlancesSensorEntityDescription(
        key="docker_cpu_use",
        type="docker",
        translation_key="container_cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_memory_use"): GlancesSensorEntityDescription(
        key="docker_memory_use",
        type="docker",
        translation_key="container_memory_used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("raid", "available"): GlancesSensorEntityDescription(
        key="available",
        type="raid",
        translation_key="raid_available",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("raid", "used"): GlancesSensorEntityDescription(
        key="used",
        type="raid",
        translation_key="raid_used",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Glances sensors."""

    coordinator: GlancesDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for sensor_type, sensors in coordinator.data.items():
        if sensor_type in ["fs", "sensors", "raid"]:
            for sensor_label, params in sensors.items():
                for param in params:
                    if sensor_description := SENSOR_TYPES.get((sensor_type, param)):
                        entities.append(
                            GlancesSensor(
                                coordinator,
                                sensor_description,
                                sensor_label,
                            )
                        )
        else:
            for sensor in sensors:
                if sensor_description := SENSOR_TYPES.get((sensor_type, sensor)):
                    entities.append(
                        GlancesSensor(
                            coordinator,
                            sensor_description,
                        )
                    )

    async_add_entities(entities)


class GlancesSensor(CoordinatorEntity[GlancesDataUpdateCoordinator], SensorEntity):
    """Implementation of a Glances sensor."""

    entity_description: GlancesSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GlancesDataUpdateCoordinator,
        description: GlancesSensorEntityDescription,
        sensor_label: str = "",
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_label = sensor_label
        self.entity_description = description
        if sensor_label:
            self._attr_translation_placeholders = {"sensor_label": sensor_label}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Glances",
            name=coordinator.host,
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{sensor_label}-{description.key}"
        )

    @property
    def available(self) -> bool:
        """Set sensor unavailable when native value is invalid."""
        if super().available:
            return (
                not self._numeric_state_expected
                or isinstance(value := self.native_value, (int, float))
                or isinstance(value, str)
                and value.isnumeric()
            )
        return False

    @property
    def native_value(self) -> StateType:
        """Return the state of the resources."""
        value = self.coordinator.data[self.entity_description.type]

        if isinstance(value.get(self._sensor_label), dict):
            return cast(
                StateType, value[self._sensor_label][self.entity_description.key]
            )
        return cast(StateType, value[self.entity_description.key])
