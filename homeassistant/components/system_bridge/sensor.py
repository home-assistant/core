"""Support for System Bridge sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast, override

from systembridgeconnector.models.modules.battery import (
    BatteryInfo,
    BatteryScope,
    BatteryState,
)
from systembridgeconnector.models.modules.cpu import PerCPU
from systembridgeconnector.models.modules.disks import Disk
from systembridgeconnector.models.modules.displays import Display
from systembridgeconnector.models.modules.gpus import GPU
from systembridgeconnector.models.modules.networks import Network, NetworkIO

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_PORT,
    REVOLUTIONS_PER_MINUTE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .data import SystemBridgeData
from .entity import SystemBridgeEntity

ATTR_AVAILABLE: Final = "available"
ATTR_FILESYSTEM: Final = "filesystem"
ATTR_MOUNT: Final = "mount"
ATTR_SIZE: Final = "size"
ATTR_TYPE: Final = "type"
ATTR_USED: Final = "used"

PIXELS: Final = "px"

PARALLEL_UPDATES = 0

BATTERY_STATE_OPTIONS: Final = [
    state.value for state in BatteryState if state is not BatteryState.UNKNOWN
]


@dataclass(frozen=True)
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


def battery_time_remaining(data: SystemBridgeData) -> datetime | None:
    """Return the battery time remaining."""
    if (battery_time := data.battery.time_remaining) is not None:
        return dt_util.utcnow() + timedelta(seconds=battery_time)
    return None


def battery_state(state: BatteryState | None) -> str | None:
    """Return the battery state, or None when it is unknown."""
    if state is None or state == BatteryState.UNKNOWN:
        return None
    return state


def with_battery(func) -> Callable:
    """Wrap a function to ensure a battery is available."""

    def wrapper(data: SystemBridgeData, name: str) -> StateType:
        """Wrap a function to ensure a battery is available."""
        for battery in data.battery.batteries:
            if battery.name == name:
                return func(battery)
        return None

    return wrapper


@with_battery
def battery_info_percentage(battery: BatteryInfo) -> float | None:
    """Return the battery level."""
    return battery.percentage


@with_battery
def battery_info_state(battery: BatteryInfo) -> str | None:
    """Return the battery state."""
    return battery_state(battery.state)


def battery_info_sensor_types(
    battery: BatteryInfo,
) -> list[SystemBridgeSensorEntityDescription]:
    """Return the sensor descriptions for a battery."""
    name = battery.name
    placeholders = {"battery": battery.model or name}
    # The main battery sensors already cover the system's own battery
    enabled_default = battery.scope == BatteryScope.DEVICE
    return [
        SystemBridgeSensorEntityDescription(
            key=f"battery_{name}",
            translation_key="battery_info",
            translation_placeholders=placeholders,
            entity_registry_enabled_default=enabled_default,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
            suggested_display_precision=0,
            value=lambda data, k=name: battery_info_percentage(data, k),
        ),
        SystemBridgeSensorEntityDescription(
            key=f"battery_{name}_state",
            translation_key="battery_info_state",
            translation_placeholders=placeholders,
            entity_registry_enabled_default=enabled_default,
            device_class=SensorDeviceClass.ENUM,
            options=BATTERY_STATE_OPTIONS,
            value=lambda data, k=name: battery_info_state(data, k),
        ),
    ]


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
    """Return the free memory, counting reclaimable cache as free."""
    if (
        data.memory is not None
        and (virtual := data.memory.virtual) is not None
        and (available := virtual.available) is not None
    ):
        return round(available / 1000**3, 2)
    return None


def memory_used(data: SystemBridgeData) -> float | None:
    """Return the used memory."""
    if (
        data.memory is not None
        and (virtual := data.memory.virtual) is not None
        and (used := virtual.used) is not None
    ):
        return round(used / 1000**3, 2)
    return None


def memory_used_percentage(data: SystemBridgeData) -> float | None:
    """Return the used memory percentage."""
    if data.memory is not None and (virtual := data.memory.virtual) is not None:
        return virtual.percent
    return None


def partition_usage(
    data: SystemBridgeData,
    device_index: int,
    partition_index: int,
) -> float | None:
    """Return the used memory."""
    if (
        data.disks is not None
        and (devices := data.disks.devices) is not None
        and device_index < len(devices)
        and (partitions := devices[device_index].partitions) is not None
        and partition_index < len(partitions)
        and (usage := partitions[partition_index].usage) is not None
    ):
        return usage.percent
    return None


def disk_read_rate(data: SystemBridgeData) -> float | None:
    """Return the read rate for all disks combined."""
    if data.disks is not None and (io := data.disks.io_counters) is not None:
        return io.read_bytes_rate
    return None


def disk_write_rate(data: SystemBridgeData) -> float | None:
    """Return the write rate for all disks combined."""
    if data.disks is not None and (io := data.disks.io_counters) is not None:
        return io.write_bytes_rate
    return None


def disk_devices(data: SystemBridgeData) -> list[Disk]:
    """Return the disk devices."""
    if data.disks is None:
        return []
    return data.disks.devices


def with_disk(func) -> Callable:
    """Wrap a function to ensure a disk is available."""

    def wrapper(data: SystemBridgeData, name: str) -> StateType:
        """Wrap a function to ensure a disk is available."""
        for disk in disk_devices(data):
            if disk.name == name:
                return func(disk)
        return None

    return wrapper


@with_disk
def disk_device_read_rate(disk: Disk) -> float | None:
    """Return the disk read rate."""
    if disk.io_counters is not None:
        return disk.io_counters.read_bytes_rate
    return None


@with_disk
def disk_device_write_rate(disk: Disk) -> float | None:
    """Return the disk write rate."""
    if disk.io_counters is not None:
        return disk.io_counters.write_bytes_rate
    return None


def disk_sensor_types(disk: Disk) -> list[SystemBridgeSensorEntityDescription]:
    """Return the sensor descriptions for a disk."""
    if disk.io_counters is None:
        return []
    name = disk.name
    return [
        SystemBridgeSensorEntityDescription(
            key=f"disk_{name}_read_rate",
            translation_key="disk_device_read_rate",
            translation_placeholders={"disk": name},
            entity_registry_enabled_default=False,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
            suggested_display_precision=2,
            value=lambda data, k=name: disk_device_read_rate(data, k),
        ),
        SystemBridgeSensorEntityDescription(
            key=f"disk_{name}_write_rate",
            translation_key="disk_device_write_rate",
            translation_placeholders={"disk": name},
            entity_registry_enabled_default=False,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
            suggested_display_precision=2,
            value=lambda data, k=name: disk_device_write_rate(data, k),
        ),
    ]


def network_io(data: SystemBridgeData) -> NetworkIO | None:
    """Return the I/O for all network interfaces combined."""
    if data.networks is not None:
        return data.networks.io
    return None


def network_download_rate(data: SystemBridgeData) -> float | None:
    """Return the download rate for all network interfaces combined."""
    if (io := network_io(data)) is not None:
        return io.bytes_recv_rate
    return None


def network_upload_rate(data: SystemBridgeData) -> float | None:
    """Return the upload rate for all network interfaces combined."""
    if (io := network_io(data)) is not None:
        return io.bytes_sent_rate
    return None


def network_interfaces(data: SystemBridgeData) -> list[Network]:
    """Return the network interfaces, leaving out loopback interfaces."""
    if data.networks is None or data.networks.networks is None:
        return []
    return [
        interface
        for interface in data.networks.networks
        if interface.name is not None
        and not (
            interface.stats is not None
            and interface.stats.flags is not None
            and "loopback" in interface.stats.flags
        )
    ]


def with_network_interface(func) -> Callable:
    """Wrap a function to ensure a network interface is available."""

    def wrapper(data: SystemBridgeData, name: str) -> StateType:
        """Wrap a function to ensure a network interface is available."""
        for interface in network_interfaces(data):
            if interface.name == name:
                return func(interface)
        return None

    return wrapper


@with_network_interface
def network_interface_download_rate(interface: Network) -> float | None:
    """Return the network interface download rate."""
    if interface.io is not None:
        return interface.io.bytes_recv_rate
    return None


@with_network_interface
def network_interface_upload_rate(interface: Network) -> float | None:
    """Return the network interface upload rate."""
    if interface.io is not None:
        return interface.io.bytes_sent_rate
    return None


@with_network_interface
def network_interface_ssid(interface: Network) -> str | None:
    """Return the SSID the network interface is connected to."""
    if interface.wifi is not None:
        return interface.wifi.ssid
    return None


@with_network_interface
def network_interface_signal_strength(interface: Network) -> int | None:
    """Return the network interface Wi-Fi signal strength."""
    if interface.wifi is not None:
        return interface.wifi.signal
    return None


@with_network_interface
def network_interface_link_rate(interface: Network) -> float | None:
    """Return the network interface Wi-Fi link rate."""
    if interface.wifi is not None:
        return interface.wifi.link_rate
    return None


def network_interface_sensor_types(
    interface: Network,
) -> list[SystemBridgeSensorEntityDescription]:
    """Return the sensor descriptions for a network interface."""
    name = cast(str, interface.name)
    descriptions = [
        SystemBridgeSensorEntityDescription(
            key=f"network_{name}_download_rate",
            translation_key="network_interface_download_rate",
            translation_placeholders={"interface": name},
            entity_registry_enabled_default=False,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
            suggested_display_precision=2,
            value=lambda data, k=name: network_interface_download_rate(data, k),
        ),
        SystemBridgeSensorEntityDescription(
            key=f"network_{name}_upload_rate",
            translation_key="network_interface_upload_rate",
            translation_placeholders={"interface": name},
            entity_registry_enabled_default=False,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
            suggested_display_precision=2,
            value=lambda data, k=name: network_interface_upload_rate(data, k),
        ),
    ]
    if interface.wifi is not None:
        descriptions.extend(
            [
                SystemBridgeSensorEntityDescription(
                    key=f"network_{name}_ssid",
                    translation_key="network_interface_ssid",
                    translation_placeholders={"interface": name},
                    value=lambda data, k=name: network_interface_ssid(data, k),
                ),
                SystemBridgeSensorEntityDescription(
                    key=f"network_{name}_signal_strength",
                    translation_key="network_interface_signal_strength",
                    translation_placeholders={"interface": name},
                    entity_category=EntityCategory.DIAGNOSTIC,
                    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                    value=lambda data, k=name: network_interface_signal_strength(
                        data, k
                    ),
                ),
                SystemBridgeSensorEntityDescription(
                    key=f"network_{name}_link_rate",
                    translation_key="network_interface_link_rate",
                    translation_placeholders={"interface": name},
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    device_class=SensorDeviceClass.DATA_RATE,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
                    suggested_display_precision=0,
                    value=lambda data, k=name: network_interface_link_rate(data, k),
                ),
            ]
        )
    return descriptions


BASE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="boot_time",
        translation_key="boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: datetime.fromtimestamp(data.system.boot_time, tz=UTC),
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_power_package",
        translation_key="cpu_power_package",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=lambda data: data.cpu.power,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_speed",
        translation_key="cpu_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.GIGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=2,
        value=cpu_speed,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
        value=lambda data: data.cpu.temperature,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_voltage",
        translation_key="cpu_voltage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value=lambda data: data.cpu.voltage,
    ),
    SystemBridgeSensorEntityDescription(
        key="disk_read_rate",
        translation_key="disk_read_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        value=disk_read_rate,
    ),
    SystemBridgeSensorEntityDescription(
        key="disk_write_rate",
        translation_key="disk_write_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        value=disk_write_rate,
    ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        translation_key="kernel",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.system.platform,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        translation_key="memory_free",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        value=memory_free,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        translation_key="memory_used_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        value=memory_used_percentage,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        translation_key="memory_used",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        value=memory_used,
    ),
    SystemBridgeSensorEntityDescription(
        key="network_download_rate",
        translation_key="network_download_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=2,
        value=network_download_rate,
    ),
    SystemBridgeSensorEntityDescription(
        key="network_upload_rate",
        translation_key="network_upload_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=2,
        value=network_upload_rate,
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        translation_key="os",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: f"{data.system.platform} {data.system.platform_version}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_count",
        translation_key="processes",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: len(data.processes),
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        translation_key="load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=1,
        value=lambda data: data.cpu.usage,
    ),
    SystemBridgeSensorEntityDescription(
        key="power_usage",
        translation_key="power_usage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value=lambda data: data.system.power_usage,
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.system.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="version_latest",
        translation_key="version_latest",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.system.version_latest,
    ),
)

LOAD_AVERAGE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="load_average",
        translation_key="load_average",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=lambda data: data.cpu.load_average,
    ),
    SystemBridgeSensorEntityDescription(
        key="load_average_5",
        translation_key="load_average_5",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=lambda data: data.cpu.load_average_5,
    ),
    SystemBridgeSensorEntityDescription(
        key="load_average_15",
        translation_key="load_average_15",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value=lambda data: data.cpu.load_average_15,
    ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        value=lambda data: data.battery.percentage,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        translation_key="battery_time_remaining",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=battery_time_remaining,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_state",
        translation_key="battery_state",
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_STATE_OPTIONS,
        value=lambda data: battery_state(data.battery.state),
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value=lambda data: data.battery.power,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value=lambda data: data.battery.voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator = entry.runtime_data

    entities = [
        SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
        for description in BASE_SENSOR_TYPES
    ]

    for index_device, device in enumerate(disk_devices(coordinator.data)):
        if device.partitions is None:
            continue

        entities.extend(
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"filesystem_{partition.mount_point.replace(':', '')}",
                    translation_key="space_used",
                    translation_placeholders={"partition": partition.mount_point},
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
                    suggested_display_precision=2,
                    value=(
                        lambda data, dk=index_device, pk=index_partition: (
                            partition_usage(data, dk, pk)
                        )
                    ),
                ),
                entry.data[CONF_PORT],
            )
            for index_partition, partition in enumerate(device.partitions)
        )

    if (
        coordinator.data.battery
        and coordinator.data.battery.percentage is not None
        and coordinator.data.battery.percentage > -1
    ):
        entities.extend(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            for description in BATTERY_SENSOR_TYPES
        )

    if coordinator.data.cpu.load_average is not None:
        entities.extend(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            for description in LOAD_AVERAGE_SENSOR_TYPES
        )

    entities.append(
        SystemBridgeSensor(
            coordinator,
            SystemBridgeSensorEntityDescription(
                key="displays_connected",
                translation_key="displays_connected",
                state_class=SensorStateClass.MEASUREMENT,
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
                        translation_key="display_resolution_x",
                        translation_placeholders={"display_id": display.id},
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PIXELS,
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
                        translation_key="display_resolution_y",
                        translation_placeholders={"display_id": display.id},
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PIXELS,
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
                        translation_key="display_refresh_rate",
                        translation_placeholders={"display_id": display.id},
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfFrequency.HERTZ,
                        device_class=SensorDeviceClass.FREQUENCY,
                        suggested_display_precision=0,
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
                        translation_key="gpu_core_clock_speed",
                        translation_placeholders={"gpu_name": gpu.name},
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
                        device_class=SensorDeviceClass.FREQUENCY,
                        suggested_display_precision=0,
                        value=lambda data, k=index: gpu_core_clock_speed(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_clock_speed",
                        translation_key="gpu_memory_clock_speed",
                        translation_placeholders={"gpu_name": gpu.name},
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
                        device_class=SensorDeviceClass.FREQUENCY,
                        suggested_display_precision=0,
                        value=lambda data, k=index: gpu_memory_clock_speed(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_free",
                        translation_key="gpu_memory_free",
                        translation_placeholders={"gpu_name": gpu.name},
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
                        device_class=SensorDeviceClass.DATA_SIZE,
                        suggested_display_precision=0,
                        value=lambda data, k=index: gpu_memory_free(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_used_percentage",
                        translation_key="gpu_memory_used_percentage",
                        translation_placeholders={"gpu_name": gpu.name},
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
                        suggested_display_precision=2,
                        value=lambda data, k=index: gpu_memory_used_percentage(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_memory_used",
                        translation_key="gpu_memory_used",
                        translation_placeholders={"gpu_name": gpu.name},
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
                        device_class=SensorDeviceClass.DATA_SIZE,
                        suggested_display_precision=0,
                        value=lambda data, k=index: gpu_memory_used(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_fan_speed",
                        translation_key="gpu_fan_speed",
                        translation_placeholders={"gpu_name": gpu.name},
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                        value=lambda data, k=index: gpu_fan_speed(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_power_usage",
                        translation_key="gpu_power_usage",
                        translation_placeholders={"gpu_name": gpu.name},
                        entity_registry_enabled_default=False,
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
                        translation_key="gpu_temperature",
                        translation_placeholders={"gpu_name": gpu.name},
                        entity_registry_enabled_default=False,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        suggested_display_precision=2,
                        value=lambda data, k=index: gpu_temperature(data, k),
                    ),
                    entry.data[CONF_PORT],
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{gpu.id}_usage_percentage",
                        translation_key="gpu_usage_percentage",
                        translation_placeholders={"gpu_name": gpu.name},
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
                        suggested_display_precision=2,
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
                            translation_key="processes_load_cpu",
                            translation_placeholders={"cpu_id": str(cpu.id)},
                            entity_registry_enabled_default=False,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
                            suggested_display_precision=2,
                            value=lambda data, k=cpu.id: cpu_usage_per_cpu(data, k),
                        ),
                        entry.data[CONF_PORT],
                    ),
                    SystemBridgeSensor(
                        coordinator,
                        SystemBridgeSensorEntityDescription(
                            key=f"cpu_power_core_{cpu.id}",
                            translation_key="cpu_power_core",
                            translation_placeholders={"cpu_id": str(cpu.id)},
                            entity_registry_enabled_default=False,
                            native_unit_of_measurement=UnitOfPower.WATT,
                            state_class=SensorStateClass.MEASUREMENT,
                            suggested_display_precision=2,
                            value=lambda data, k=cpu.id: cpu_power_per_cpu(data, k),
                        ),
                        entry.data[CONF_PORT],
                    ),
                ]
            )

    async_add_entities(entities)

    known_dynamic_sensors: set[str] = set()

    @callback
    def _async_add_dynamic_sensors() -> None:
        """Add disk and network interface sensors not seen before."""
        descriptions = [
            *(
                description
                for disk in disk_devices(coordinator.data)
                for description in disk_sensor_types(disk)
            ),
            *(
                description
                for interface in network_interfaces(coordinator.data)
                for description in network_interface_sensor_types(interface)
            ),
        ]
        new_descriptions = [
            description
            for description in descriptions
            if description.key not in known_dynamic_sensors
        ]
        if not new_descriptions:
            return
        known_dynamic_sensors.update(
            description.key for description in new_descriptions
        )
        async_add_entities(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            for description in new_descriptions
        )

    _async_add_dynamic_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_dynamic_sensors))

    known_battery_sensors: set[str] = set()

    @callback
    def _async_add_battery_sensors() -> None:
        """Add battery sensors not seen before."""
        new_descriptions = [
            description
            for battery in coordinator.data.battery.batteries
            for description in battery_info_sensor_types(battery)
            if description.key not in known_battery_sensors
        ]
        if not new_descriptions:
            return
        known_battery_sensors.update(
            description.key for description in new_descriptions
        )
        async_add_entities(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            for description in new_descriptions
        )

    _async_add_battery_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_battery_sensors))


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

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state."""
        try:
            return cast(StateType, self.entity_description.value(self.coordinator.data))
        except TypeError:
            return None
