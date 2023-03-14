"""Support for System Bridge sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, cast

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
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from . import SystemBridgeEntity
from .const import DOMAIN
from .coordinator import SystemBridgeCoordinatorData, SystemBridgeDataUpdateCoordinator

ATTR_AVAILABLE: Final = "available"
ATTR_FILESYSTEM: Final = "filesystem"
ATTR_MOUNT: Final = "mount"
ATTR_SIZE: Final = "size"
ATTR_TYPE: Final = "type"
ATTR_USED: Final = "used"

PIXELS: Final = "px"


@dataclass
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


def battery_time_remaining(data: SystemBridgeCoordinatorData) -> datetime | None:
    """Return the battery time remaining."""
    if (value := getattr(data.battery, "sensors_secsleft", None)) is not None:
        return utcnow() + timedelta(seconds=value)
    return None


def cpu_speed(data: SystemBridgeCoordinatorData) -> float | None:
    """Return the CPU speed."""
    if data.cpu.frequency_current is not None:
        return round(data.cpu.frequency_current / 1000, 2)
    return None


def gpu_core_clock_speed(data: SystemBridgeCoordinatorData, key: str) -> float | None:
    """Return the GPU core clock speed."""
    if (value := getattr(data.gpu, f"{key}_core_clock", None)) is not None:
        return round(value)
    return None


def gpu_memory_clock_speed(data: SystemBridgeCoordinatorData, key: str) -> float | None:
    """Return the GPU memory clock speed."""
    if (value := getattr(data.gpu, f"{key}_memory_clock", None)) is not None:
        return round(value)
    return None


def gpu_memory_free(data: SystemBridgeCoordinatorData, key: str) -> float | None:
    """Return the free GPU memory."""
    if (value := getattr(data.gpu, f"{key}_memory_free", None)) is not None:
        return round(value)
    return None


def gpu_memory_used(data: SystemBridgeCoordinatorData, key: str) -> float | None:
    """Return the used GPU memory."""
    if (value := getattr(data.gpu, f"{key}_memory_used", None)) is not None:
        return round(value)
    return None


def gpu_memory_used_percentage(
    data: SystemBridgeCoordinatorData, key: str
) -> float | None:
    """Return the used GPU memory percentage."""
    if ((used := getattr(data.gpu, f"{key}_memory_used", None)) is not None) and (
        (total := getattr(data.gpu, f"{key}_memory_total", None)) is not None
    ):
        return round(
            used / total * 100,
            2,
        )
    return None


def memory_free(data: SystemBridgeCoordinatorData) -> float | None:
    """Return the free memory."""
    if data.memory.virtual_free is not None:
        return round(data.memory.virtual_free / 1000**3, 2)
    return None


def memory_used(data: SystemBridgeCoordinatorData) -> float | None:
    """Return the used memory."""
    if data.memory.virtual_used is not None:
        return round(data.memory.virtual_used / 1000**3, 2)
    return None


BASE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="boot_time",
        name="Boot time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:av-timer",
        value=lambda data: datetime.fromtimestamp(
            data.system.boot_time, tz=timezone.utc
        ),
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_speed",
        name="CPU speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.GIGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        icon="mdi:speedometer",
        value=cpu_speed,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_temperature",
        name="CPU temperature",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda data: data.cpu.temperature,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_voltage",
        name="CPU voltage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: data.cpu.voltage,
    ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        name="Kernel",
        icon="mdi:devices",
        value=lambda data: data.system.platform,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        name="Memory free",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        value=memory_free,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        name="Memory used %",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        value=lambda data: data.memory.virtual_percent,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        name="Memory used",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        value=memory_used,
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        name="Operating system",
        icon="mdi:devices",
        value=lambda data: f"{data.system.platform} {data.system.platform_version}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        name="Load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda data: data.cpu.usage,
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        name="Version",
        icon="mdi:counter",
        value=lambda data: data.system.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="version_latest",
        name="Latest version",
        icon="mdi:counter",
        value=lambda data: data.system.version_latest,
    ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: data.battery.percentage,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        name="Battery time remaining",
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

    entities = []
    for description in BASE_SENSOR_TYPES:
        entities.append(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
        )

    for partition in coordinator.data.disk.partitions:
        entities.append(
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"filesystem_{partition.replace(':', '')}",
                    name=f"{partition} space used",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:harddisk",
                    value=lambda data, p=partition: getattr(
                        data.disk, f"usage_{p}_percent", None
                    ),
                ),
                entry.data[CONF_PORT],
            )
        )

    if (
        coordinator.data.battery
        and coordinator.data.battery.percentage
        and coordinator.data.battery.percentage > -1
    ):
        for description in BATTERY_SENSOR_TYPES:
            entities.append(
                SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            )

    displays: list[dict[str, str]] = []
    if coordinator.data.display.displays is not None:
        displays.extend(
            {
                "key": display,
                "name": getattr(coordinator.data.display, f"{display}_name").replace(
                    "Display ", ""
                ),
            }
            for display in coordinator.data.display.displays
            if hasattr(coordinator.data.display, f"{display}_name")
        )
    display_count = len(displays)

    entities.append(
        SystemBridgeSensor(
            coordinator,
            SystemBridgeSensorEntityDescription(
                key="displays_connected",
                name="Displays connected",
                state_class=SensorStateClass.MEASUREMENT,
                icon="mdi:monitor",
                value=lambda _, count=display_count: count,
            ),
            entry.data[CONF_PORT],
        )
    )

    for _, display in enumerate(displays):
        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"display_{display['name']}_resolution_x",
                    name=f"Display {display['name']} resolution x",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PIXELS,
                    icon="mdi:monitor",
                    value=lambda data, k=display["key"]: getattr(
                        data.display, f"{k}_resolution_horizontal", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"display_{display['name']}_resolution_y",
                    name=f"Display {display['name']} resolution y",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PIXELS,
                    icon="mdi:monitor",
                    value=lambda data, k=display["key"]: getattr(
                        data.display, f"{k}_resolution_vertical", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"display_{display['name']}_refresh_rate",
                    name=f"Display {display['name']} refresh rate",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfFrequency.HERTZ,
                    device_class=SensorDeviceClass.FREQUENCY,
                    icon="mdi:monitor",
                    value=lambda data, k=display["key"]: getattr(
                        data.display, f"{k}_refresh_rate", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
        ]

    gpus: list[dict[str, str]] = []
    if coordinator.data.gpu.gpus is not None:
        gpus.extend(
            {
                "key": gpu,
                "name": getattr(coordinator.data.gpu, f"{gpu}_name"),
            }
            for gpu in coordinator.data.gpu.gpus
            if hasattr(coordinator.data.gpu, f"{gpu}_name")
        )

    for index, gpu in enumerate(gpus):
        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_core_clock_speed",
                    name=f"{gpu['name']} clock speed",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
                    device_class=SensorDeviceClass.FREQUENCY,
                    icon="mdi:speedometer",
                    value=lambda data, k=gpu["key"]: gpu_core_clock_speed(data, k),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_clock_speed",
                    name=f"{gpu['name']} memory clock speed",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
                    device_class=SensorDeviceClass.FREQUENCY,
                    icon="mdi:speedometer",
                    value=lambda data, k=gpu["key"]: gpu_memory_clock_speed(data, k),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_free",
                    name=f"{gpu['name']} memory free",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfInformation.GIGABYTES,
                    device_class=SensorDeviceClass.DATA_SIZE,
                    icon="mdi:memory",
                    value=lambda data, k=gpu["key"]: gpu_memory_free(data, k),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_used_percentage",
                    name=f"{gpu['name']} memory used %",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:memory",
                    value=lambda data, k=gpu["key"]: gpu_memory_used_percentage(
                        data, k
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_used",
                    name=f"{gpu['name']} memory used",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfInformation.GIGABYTES,
                    device_class=SensorDeviceClass.DATA_SIZE,
                    icon="mdi:memory",
                    value=lambda data, k=gpu["key"]: gpu_memory_used(data, k),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_fan_speed",
                    name=f"{gpu['name']} fan speed",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                    icon="mdi:fan",
                    value=lambda data, k=gpu["key"]: getattr(
                        data.gpu, f"{k}_fan_speed", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_power_usage",
                    name=f"{gpu['name']} power usage",
                    entity_registry_enabled_default=False,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfPower.WATT,
                    value=lambda data, k=gpu["key"]: getattr(
                        data.gpu, f"{k}_power", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_temperature",
                    name=f"{gpu['name']} temperature",
                    entity_registry_enabled_default=False,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    value=lambda data, k=gpu["key"]: getattr(
                        data.gpu, f"{k}_temperature", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_usage_percentage",
                    name=f"{gpu['name']} usage %",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda data, k=gpu["key"]: getattr(
                        data.gpu, f"{k}_core_load", None
                    ),
                ),
                entry.data[CONF_PORT],
            ),
        ]

    for index in range(coordinator.data.cpu.count):
        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}",
                    name=f"Load CPU {index}",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda data, k=index: getattr(data.cpu, f"usage_{k}", None),
                ),
                entry.data[CONF_PORT],
            ),
        ]

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
            description.name,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        try:
            return cast(StateType, self.entity_description.value(self.coordinator.data))
        except TypeError:
            return None
