"""Support for System Bridge sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

from systembridgemodels.modules.cpu import PerCPU
from systembridgemodels.modules.displays import Display
from systembridgemodels.modules.gpus import GPU

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator
from .data import SystemBridgeData
from .entity import SystemBridgeEntity

ATTR_AVAILABLE: Final = "available"
ATTR_FILESYSTEM: Final = "filesystem"
ATTR_MOUNT: Final = "mount"
ATTR_SIZE: Final = "size"
ATTR_TYPE: Final = "type"
ATTR_USED: Final = "used"

PIXELS: Final = "px"


@dataclass(frozen=True)
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


def battery_time_remaining(data: SystemBridgeData) -> datetime | None:
    """Return the battery time remaining."""
    if (battery_time := data.battery.time_remaining) is not None:
        return dt_util.utcnow() + timedelta(seconds=battery_time)
    return None


def cpu_speed(data: SystemBridgeData) -> float | None:
    """Return the CPU speed."""
    if (cpu_frequency := data.cpu.frequency) is not None and (
        cpu_frequency.current
    ) is not None:
        return round(cpu_frequency.current / 1000, 2)
    return None


def with_per_cpu(func) -> Callable:
    """Wrap a function to ensure per CPU data is available."""

    def wrapper(data: SystemBridgeData, index: int) -> float | None:
        """Wrap a function to ensure per CPU data is available."""
        if data.cpu.per_cpu is not None and index < len(data.cpu.per_cpu):
            return func(data.cpu.per_cpu[index])
        return None

    return wrapper


@with_per_cpu
def cpu_power_per_cpu(per_cpu: PerCPU) -> float | None:
    """Return CPU power per CPU."""
    return per_cpu.power


@with_per_cpu
def cpu_usage_per_cpu(per_cpu: PerCPU) -> float | None:
    """Return CPU usage per CPU."""
    return per_cpu.usage


def with_display(func) -> Callable:
    """Wrap a function to ensure a Display is available."""

    def wrapper(data: SystemBridgeData, index: int) -> Display | None:
        """Wrap a function to ensure a Display is available."""
        if index < len(data.displays):
            return func(data.displays[index])
        return None

    return wrapper


@with_display
def display_resolution_horizontal(display: Display) -> int | None:
    """Return the Display resolution horizontal."""
    return display.resolution_horizontal


@with_display
def display_resolution_vertical(display: Display) -> int | None:
    """Return the Display resolution vertical."""
    return display.resolution_vertical


@with_display
def display_refresh_rate(display: Display) -> float | None:
    """Return the Display refresh rate."""
    return display.refresh_rate


def with_gpu(func) -> Callable:
    """Wrap a function to ensure a GPU is available."""

    def wrapper(data: SystemBridgeData, index: int) -> GPU | None:
        """Wrap a function to ensure a GPU is available."""
        if index < len(data.gpus):
            return func(data.gpus[index])
        return None

    return wrapper


@with_gpu
def gpu_core_clock_speed(gpu: GPU) -> float | None:
    """Return the GPU core clock speed."""
    return gpu.core_clock


@with_gpu
def gpu_fan_speed(gpu: GPU) -> float | None:
    """Return the GPU fan speed."""
    return gpu.fan_speed


@with_gpu
def gpu_memory_clock_speed(gpu: GPU) -> float | None:
    """Return the GPU memory clock speed."""
    return gpu.memory_clock


@with_gpu
def gpu_memory_free(gpu: GPU) -> float | None:
    """Return the free GPU memory."""
    return gpu.memory_free


@with_gpu
def gpu_memory_used(gpu: GPU) -> float | None:
    """Return the used GPU memory."""
    return gpu.memory_used


@with_gpu
def gpu_memory_used_percentage(gpu: GPU) -> float | None:
    """Return the used GPU memory percentage."""
    if (gpu.memory_used) is not None and (gpu.memory_total) is not None:
        return round(gpu.memory_used / gpu.memory_total * 100, 2)
    return None


@with_gpu
def gpu_power_usage(gpu: GPU) -> float | None:
    """Return the GPU power usage."""
    return gpu.power_usage


@with_gpu
def gpu_temperature(gpu: GPU) -> float | None:
    """Return the GPU temperature."""
    return gpu.temperature


@with_gpu
def gpu_usage_percentage(gpu: GPU) -> float | None:
    """Return the GPU usage percentage."""
    return gpu.core_load


def memory_free(data: SystemBridgeData) -> float | None:
    """Return the free memory."""
    if (virtual := data.memory.virtual) is not None and (
        free := virtual.free
    ) is not None:
        return round(free / 1000**3, 2)
    return None


def memory_used(data: SystemBridgeData) -> float | None:
    """Return the used memory."""
    if (virtual := data.memory.virtual) is not None and (
        used := virtual.used
    ) is not None:
        return round(used / 1000**3, 2)
    return None


def partition_usage(
    data: SystemBridgeData,
    device_index: int,
    partition_index: int,
) -> float | None:
    """Return the used memory."""
    if (
        (devices := data.disks.devices) is not None
        and device_index < len(devices)
        and (partitions := devices[device_index].partitions) is not None
        and partition_index < len(partitions)
        and (usage := partitions[partition_index].usage) is not None
    ):
        return usage.percent
    return None


BASE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="boot_time",
        translation_key="boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:av-timer",
        value=lambda data: datetime.fromtimestamp(data.system.boot_time, tz=UTC),
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_power_package",
        translation_key="cpu_power_package",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:chip",
        value=lambda data: data.cpu.power,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_speed",
        translation_key="cpu_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.GIGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        icon="mdi:speedometer",
        value=cpu_speed,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda data: data.cpu.temperature,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_voltage",
        translation_key="cpu_voltage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: data.cpu.voltage,
    ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        translation_key="kernel",
        icon="mdi:devices",
        value=lambda data: data.system.platform,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        translation_key="memory_free",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        value=memory_free,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        value=lambda data: data.memory.virtual.percent,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        translation_key="memory_used",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        value=memory_used,
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        translation_key="os",
        icon="mdi:devices",
        value=lambda data: f"{data.system.platform} {data.system.platform_version}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_count",
        translation_key="processes",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        value=lambda data: len(data.processes),
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        translation_key="load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda data: data.cpu.usage,
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        translation_key="version",
        icon="mdi:counter",
        value=lambda data: data.system.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="version_latest",
        translation_key="version_latest",
        icon="mdi:counter",
        value=lambda data: data.system.version_latest,
    ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: data.battery.percentage,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        translation_key="battery_time_remaining",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=battery_time_remaining,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
        for description in BASE_SENSOR_TYPES
    ]

    for index_device, device in enumerate(coordinator.data.disks.devices):
        if device.partitions is None:
            continue

        entities.extend(
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"filesystem_{partition.mount_point.replace(':', '')}",
                    name=f"{partition.mount_point} space used",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:harddisk",
                    value=(
                        lambda data,
                        dk=index_device,
                        pk=index_partition: partition_usage(data, dk, pk)
                    ),
                ),
                entry.data[CONF_PORT],
            )
            for index_partition, partition in enumerate(device.partitions)
        )

    if (
        coordinator.data.battery
        and coordinator.data.battery.percentage
        and coordinator.data.battery.percentage > -1
    ):
        entities.extend(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            for description in BATTERY_SENSOR_TYPES
        )

    entities.append(
        SystemBridgeSensor(
            coordinator,
            SystemBridgeSensorEntityDescription(
                key="displays_connected",
                translation_key="displays_connected",
                state_class=SensorStateClass.MEASUREMENT,
                icon="mdi:monitor",
                value=lambda data: len(data.displays) if data.displays else None,
            ),
            entry.data[CONF_PORT],
        )
    )

    if coordinator.data.displays is not None:
        for index, display in enumerate(coordinator.data.displays):
            entities = [
                *entities,
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"display_{display.id}_resolution_x",
                        name=f"Display {display.id} resolution x",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PIXELS,
                        icon="mdi:monitor",
                        value=lambda data, k=index: display_resolution_horizontal(
                            data, k
                        ),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"display_{display.id}_resolution_y",
                        name=f"Display {display.id} resolution y",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PIXELS,
                        icon="mdi:monitor",
                        value=lambda data, k=index: display_resolution_vertical(
                            data, k
                        ),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"display_{display.id}_refresh_rate",
                        name=f"Display {display.id} refresh rate",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfFrequency.HERTZ,
                        device_class=SensorDeviceClass.FREQUENCY,
                        icon="mdi:monitor",
                        value=lambda data, k=index: display_refresh_rate(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
            ]

    for index, gpu in enumerate(coordinator.data.gpus):
        entities.extend(
            [
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_core_clock_speed",
                        name=f"{gpu.name} clock speed",
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
                        device_class=SensorDeviceClass.FREQUENCY,
                        icon="mdi:speedometer",
                        value=lambda data, k=index: gpu_core_clock_speed(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_clock_speed",
                        name=f"{gpu.name} memory clock speed",
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
                        device_class=SensorDeviceClass.FREQUENCY,
                        icon="mdi:speedometer",
                        value=lambda data, k=index: gpu_memory_clock_speed(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_free",
                        name=f"{gpu.name} memory free",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
                        device_class=SensorDeviceClass.DATA_SIZE,
                        icon="mdi:memory",
                        value=lambda data, k=index: gpu_memory_free(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_used_percentage",
                        name=f"{gpu.name} memory used %",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:memory",
                        value=lambda data, k=index: gpu_memory_used_percentage(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_used",
                        name=f"{gpu.name} memory used",
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
                        device_class=SensorDeviceClass.DATA_SIZE,
                        icon="mdi:memory",
                        value=lambda data, k=index: gpu_memory_used(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_fan_speed",
                        name=f"{gpu.name} fan speed",
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                        icon="mdi:fan",
                        value=lambda data, k=index: gpu_fan_speed(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_power_usage",
                        name=f"{gpu.name} power usage",
                        entity_registry_enabled_default=False,
                        device_class=SensorDeviceClass.POWER,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfPower.WATT,
                        value=lambda data, k=index: gpu_power_usage(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_temperature",
                        name=f"{gpu.name} temperature",
                        entity_registry_enabled_default=False,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        value=lambda data, k=index: gpu_temperature(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_usage_percentage",
                        name=f"{gpu.name} usage %",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:percent",
                        value=lambda data, k=index: gpu_usage_percentage(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
            ]
        )

    if coordinator.data.cpu.per_cpu is not None:
        for cpu in coordinator.data.cpu.per_cpu:
            entities.extend(
                [
                    SystemBridgeSensor(
                        coordinator,
                        SystemBridgeSensorEntityDescription(
                            key=f"processes_load_cpu_{cpu.id}",
                            name=f"Load CPU {cpu.id}",
                            entity_registry_enabled_default=False,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=PERCENTAGE,
                            icon="mdi:percent",
                            value=lambda data, k=cpu.id: cpu_usage_per_cpu(data, k),
                        ),
                        entry.data[CONF_PORT],
                    ),
                    SystemBridgeSensor(
                        coordinator,
                        SystemBridgeSensorEntityDescription(
                            key=f"cpu_power_core_{cpu.id}",
                            name=f"CPU Core {cpu.id} Power",
                            entity_registry_enabled_default=False,
                            native_unit_of_measurement=UnitOfPower.WATT,
                            state_class=SensorStateClass.MEASUREMENT,
                            icon="mdi:chip",
                            value=lambda data, k=cpu.id: cpu_power_per_cpu(data, k),
                        ),
                        entry.data[CONF_PORT],
                    ),
                ]
            )

    async_add_entities(entities)


class SystemBridgeSensor(SystemBridgeEntity, SensorEntity):
    """Define a System Bridge sensor."""

    entity_description: SystemBridgeSensorEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeSensorEntityDescription,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api_port,
            description.key,
        )
        self.entity_description = description
        if description.name != UNDEFINED:
            self._attr_has_entity_name = False

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        try:
            return cast(StateType, self.entity_description.value(self.coordinator.data))
        except TypeError:
            return None
