"""Support for System Bridge sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, cast

from systembridge import Bridge

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_GIGAHERTZ,
    FREQUENCY_MEGAHERTZ,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType

from . import SystemBridgeDeviceEntity
from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

ATTR_AVAILABLE: Final = "available"
ATTR_FILESYSTEM: Final = "filesystem"
ATTR_MOUNT: Final = "mount"
ATTR_SIZE: Final = "size"
ATTR_TYPE: Final = "type"
ATTR_USED: Final = "used"


@dataclass
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


BASE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="bios_version",
        name="BIOS Version",
        entity_registry_enabled_default=False,
        icon="mdi:chip",
        value=lambda bridge: bridge.system.bios.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_speed",
        name="CPU Speed",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=FREQUENCY_GIGAHERTZ,
        icon="mdi:speedometer",
        value=lambda bridge: bridge.cpu.currentSpeed.avg,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_temperature",
        name="CPU Temperature",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda bridge: bridge.cpu.temperature.main,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_voltage",
        name="CPU Voltage",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda bridge: bridge.cpu.cpu.voltage,
    ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        name="Kernel",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:devices",
        value=lambda bridge: bridge.os.kernel,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        name="Memory Free",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda bridge: round(bridge.memory.free / 1000 ** 3, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        name="Memory Used %",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        value=lambda bridge: round((bridge.memory.used / bridge.memory.total) * 100, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        name="Memory Used",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda bridge: round(bridge.memory.used / 1000 ** 3, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        name="Operating System",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:devices",
        value=lambda bridge: f"{bridge.os.distro} {bridge.os.release}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        name="Load",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoad, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load_idle",
        name="Idle Load",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoadIdle, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load_system",
        name="System Load",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoadSystem, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load_user",
        name="User Load",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoadUser, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        name="Version",
        icon="mdi:counter",
        value=lambda bridge: bridge.information.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="version_latest",
        name="Latest Version",
        icon="mdi:counter",
        value=lambda bridge: bridge.information.updates.version.new,
    ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda bridge: bridge.battery.percent,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        name="Battery Time Remaining",
        device_class=DEVICE_CLASS_TIMESTAMP,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda bridge: str(
            datetime.now() + timedelta(minutes=bridge.battery.timeRemaining)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for description in BASE_SENSOR_TYPES:
        entities.append(SystemBridgeSensor(coordinator, description))

    for key, _ in coordinator.data.filesystem.fsSize.items():
        uid = key.replace(":", "")
        entities.append(
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"filesystem_{uid}",
                    name=f"{key} Space Used",
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:harddisk",
                    value=lambda bridge, i=key: round(
                        bridge.filesystem.fsSize[i]["use"], 2
                    ),
                ),
            )
        )

    if coordinator.data.battery.hasBattery:
        for description in BATTERY_SENSOR_TYPES:
            entities.append(SystemBridgeSensor(coordinator, description))

    for index, _ in enumerate(coordinator.data.graphics.controllers):
        if coordinator.data.graphics.controllers[index].name is not None:
            # Remove vendor from name
            name = (
                coordinator.data.graphics.controllers[index]
                .name.replace(coordinator.data.graphics.controllers[index].vendor, "")
                .strip()
            )
            entities = [
                *entities,
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_core_clock_speed",
                        name=f"{name} Clock Speed",
                        entity_registry_enabled_default=False,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
                        icon="mdi:speedometer",
                        value=lambda bridge, i=index: bridge.graphics.controllers[
                            i
                        ].clockCore,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_memory_clock_speed",
                        name=f"{name} Memory Clock Speed",
                        entity_registry_enabled_default=False,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
                        icon="mdi:speedometer",
                        value=lambda bridge, i=index: bridge.graphics.controllers[
                            i
                        ].clockMemory,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_memory_free",
                        name=f"{name} Memory Free",
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=DATA_GIGABYTES,
                        icon="mdi:memory",
                        value=lambda bridge, i=index: round(
                            bridge.graphics.controllers[i].memoryFree / 10 ** 3, 2
                        ),
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_memory_used_percentage",
                        name=f"{name} Memory Used %",
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:memory",
                        value=lambda bridge, i=index: round(
                            (
                                bridge.graphics.controllers[i].memoryUsed
                                / bridge.graphics.controllers[i].memoryTotal
                            )
                            * 100,
                            2,
                        ),
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_memory_used",
                        name=f"{name} Memory Used",
                        entity_registry_enabled_default=False,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=DATA_GIGABYTES,
                        icon="mdi:memory",
                        value=lambda bridge, i=index: round(
                            bridge.graphics.controllers[i].memoryUsed / 10 ** 3, 2
                        ),
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_fan_speed",
                        name=f"{name} Fan Speed",
                        entity_registry_enabled_default=False,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:fan",
                        value=lambda bridge, i=index: bridge.graphics.controllers[
                            i
                        ].fanSpeed,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_power_usage",
                        name=f"{name} Power Usage",
                        entity_registry_enabled_default=False,
                        device_class=DEVICE_CLASS_POWER,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=POWER_WATT,
                        value=lambda bridge, i=index: bridge.graphics.controllers[
                            i
                        ].powerDraw,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_temperature",
                        name=f"{name} Temperature",
                        entity_registry_enabled_default=False,
                        device_class=DEVICE_CLASS_TEMPERATURE,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=TEMP_CELSIUS,
                        value=lambda bridge, i=index: bridge.graphics.controllers[
                            i
                        ].temperatureGpu,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{index}_usage_percentage",
                        name=f"{name} Usage %",
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:percent",
                        value=lambda bridge, i=index: bridge.graphics.controllers[
                            i
                        ].utilizationGpu,
                    ),
                ),
            ]

    for index, _ in enumerate(coordinator.data.processes.load.cpus):
        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}",
                    name=f"Load CPU {index}",
                    entity_registry_enabled_default=False,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge, index=index: round(
                        bridge.processes.load.cpus[index].load, 2
                    ),
                ),
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}_idle",
                    name=f"Idle Load CPU {index}",
                    entity_registry_enabled_default=False,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge, index=index: round(
                        bridge.processes.load.cpus[index].loadIdle, 2
                    ),
                ),
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}_system",
                    name=f"System Load CPU {index}",
                    entity_registry_enabled_default=False,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge, index=index: round(
                        bridge.processes.load.cpus[index].loadSystem, 2
                    ),
                ),
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}_user",
                    name=f"User Load CPU {index}",
                    entity_registry_enabled_default=False,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge, index=index: round(
                        bridge.processes.load.cpus[index].loadUser, 2
                    ),
                ),
            ),
        ]

    async_add_entities(entities)


class SystemBridgeSensor(SystemBridgeDeviceEntity, SensorEntity):
    """Define a System Bridge sensor."""

    coordinator: SystemBridgeDataUpdateCoordinator
    entity_description: SystemBridgeSensorEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            description.key,
            description.name,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        bridge: Bridge = self.coordinator.data
        try:
            return cast(StateType, self.entity_description.value(bridge))
        except TypeError:
            return None
