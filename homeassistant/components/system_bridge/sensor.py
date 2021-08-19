"""Support for System Bridge sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final, cast

from systembridge import Bridge

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
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
from .model import SystemBridgeSensorEntityDescription

ATTR_AVAILABLE: Final = "available"
ATTR_FILESYSTEM: Final = "filesystem"
ATTR_MOUNT: Final = "mount"
ATTR_SIZE: Final = "size"
ATTR_TYPE: Final = "type"
ATTR_USED: Final = "used"


BASE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="bios_version",
        name="BIOS Version",
        enabled_by_default=False,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=None,
        icon="mdi:chip",
        value=lambda bridge: bridge.system.bios.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_speed",
        name="CPU Speed",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=FREQUENCY_GIGAHERTZ,
        icon="mdi:speedometer",
        value=lambda bridge: bridge.cpu.currentSpeed.avg,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_temperature",
        name="CPU Temperature",
        enabled_by_default=False,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        value=lambda bridge: bridge.cpu.temperature.main,
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_voltage",
        name="CPU Voltage",
        enabled_by_default=False,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon=None,
        value=lambda bridge: bridge.cpu.cpu.voltage,
    ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        name="Kernel",
        device_class=None,
        enabled_by_default=True,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=None,
        icon="mdi:devices",
        value=lambda bridge: bridge.os.kernel,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        name="Memory Free",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda bridge: round(bridge.memory.free / 1000 ** 3, 2)
        if bridge.memory.free is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        name="Memory Used %",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        value=lambda bridge: round((bridge.memory.used / bridge.memory.total) * 100, 2)
        if bridge.memory.used is not None and bridge.memory.total is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        name="Memory Used",
        enabled_by_default=False,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda bridge: round(bridge.memory.used / 1000 ** 3, 2)
        if bridge.memory.used is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        name="Operating System",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=None,
        icon="mdi:devices",
        value=lambda bridge: f"{bridge.os.distro} {bridge.os.release}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        name="Load",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoad, 2)
        if bridge.processes.load.currentLoad is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load_idle",
        name="Idle Load",
        enabled_by_default=False,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoadIdle, 2)
        if bridge.processes.load.currentLoadIdle is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load_system",
        name="System Load",
        enabled_by_default=False,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoadSystem, 2)
        if bridge.processes.load.currentLoadSystem is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load_user",
        name="User Load",
        enabled_by_default=False,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda bridge: round(bridge.processes.load.currentLoadUser, 2)
        if bridge.processes.load.currentLoadUser is not None
        else None,
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        name="Version",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=None,
        icon="mdi:counter",
        value=lambda bridge: bridge.information.version,
    ),
    SystemBridgeSensorEntityDescription(
        key="version_latest",
        name="Latest Version",
        enabled_by_default=True,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=None,
        icon="mdi:counter",
        value=lambda bridge: bridge.information.updates.version.new
        if bridge.information.updates is not None
        else None,
    ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        name="Battery",
        enabled_by_default=True,
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
        value=lambda bridge: bridge.battery.percent,
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        name="Battery Time Remaining",
        enabled_by_default=True,
        device_class=DEVICE_CLASS_TIMESTAMP,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=None,
        icon=None,
        value=lambda bridge: str(
            datetime.now() + timedelta(minutes=bridge.battery.timeRemaining)
        )
        if bridge.battery.timeRemaining is not None
        else None,
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
                    enabled_by_default=True,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:harddisk",
                    value=lambda bridge: round(bridge.filesystem.fsSize[key]["use"], 2)
                    if bridge.filesystem.fsSize[key]["use"] is not None
                    else None,
                ),
            )
        )

    if coordinator.data.battery.hasBattery:
        for description in BATTERY_SENSOR_TYPES:
            entities.append(SystemBridgeSensor(coordinator, description))

    for index, _ in enumerate(coordinator.data.graphics.controllers):
        i = index
        if coordinator.data.graphics.controllers[i].name is not None:
            # Remove vendor from name
            name = (
                coordinator.data.graphics.controllers[i]
                .name.replace(coordinator.data.graphics.controllers[i].vendor, "")
                .strip()
            )
            entities = [
                *entities,
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_core_clock_speed",
                        name=f"{name} Clock Speed",
                        enabled_by_default=False,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
                        icon="mdi:speedometer",
                        value=lambda bridge: bridge.graphics.controllers[i].clockCore,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_memory_clock_speed",
                        name=f"{name} Memory Clock Speed",
                        enabled_by_default=False,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
                        icon="mdi:speedometer",
                        value=lambda bridge: bridge.graphics.controllers[i].clockMemory
                        if bridge.graphics.controllers[i].clockMemory is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_memory_free",
                        name=f"{name} Memory Free",
                        enabled_by_default=True,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=DATA_GIGABYTES,
                        icon="mdi:memory",
                        value=lambda bridge: round(
                            bridge.graphics.controllers[i].memoryFree / 10 ** 3, 2
                        )
                        if bridge.graphics.controllers[i].memoryFree is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_memory_used_percentage",
                        name=f"{name} Memory Used %",
                        enabled_by_default=True,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=DATA_GIGABYTES,
                        icon="mdi:memory",
                        value=lambda bridge: round(
                            (
                                bridge.graphics.controllers[i].memoryUsed
                                / bridge.graphics.controllers[i].memoryTotal
                            )
                            * 100,
                            2,
                        )
                        if bridge.graphics.controllers[i].memoryUsed is not None
                        and bridge.graphics.controllers[i].memoryTotal is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_memory_used",
                        name=f"{name} Memory Used",
                        enabled_by_default=False,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=DATA_GIGABYTES,
                        icon="mdi:memory",
                        value=lambda bridge: round(
                            bridge.graphics.controllers[i].memoryUsed / 10 ** 3, 2
                        )
                        if bridge.graphics.controllers[i].memoryUsed is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_fan_speed",
                        name=f"{name} Fan Speed",
                        enabled_by_default=False,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:fan",
                        value=lambda bridge: bridge.graphics.controllers[i].fanSpeed
                        if bridge.graphics.controllers[i].fanSpeed is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_power_usage",
                        name=f"{name} Power Usage",
                        enabled_by_default=False,
                        device_class=DEVICE_CLASS_POWER,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=POWER_WATT,
                        icon=None,
                        value=lambda bridge: bridge.graphics.controllers[i].powerDraw
                        if bridge.graphics.controllers[i].powerDraw is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_temperature",
                        name=f"{name} Temperature",
                        enabled_by_default=False,
                        device_class=DEVICE_CLASS_TEMPERATURE,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=TEMP_CELSIUS,
                        icon=None,
                        value=lambda bridge: bridge.graphics.controllers[
                            i
                        ].temperatureGpu
                        if bridge.graphics.controllers[i].temperatureGpu is not None
                        else None,
                    ),
                ),
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"gpu_{i}_usage_percentage",
                        name=f"{name} Usage %",
                        enabled_by_default=True,
                        device_class=None,
                        state_class=STATE_CLASS_MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:percent",
                        value=lambda bridge: bridge.graphics.controllers[
                            i
                        ].utilizationGpu
                        if bridge.graphics.controllers[i].utilizationGpu is not None
                        else None,
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
                    enabled_by_default=False,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge: round(
                        bridge.processes.load.cpus[index].load, 2
                    )
                    if bridge.processes.load.cpus[index].load is not None
                    else None,
                ),
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}_idle",
                    name=f"Idle Load CPU {index}",
                    enabled_by_default=False,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge: round(
                        bridge.processes.load.cpus[index].loadIdle, 2
                    )
                    if bridge.processes.load.cpus[index].loadIdle is not None
                    else None,
                ),
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}_system",
                    name=f"System Load CPU {index}",
                    enabled_by_default=False,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge: round(
                        bridge.processes.load.cpus[index].loadSystem, 2
                    )
                    if bridge.processes.load.cpus[index].loadSystem is not None
                    else None,
                ),
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}_user",
                    name=f"User Load CPU {index}",
                    enabled_by_default=False,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda bridge: round(
                        bridge.processes.load.cpus[index].loadUser, 2
                    )
                    if bridge.processes.load.cpus[index].loadUser is not None
                    else None,
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
            description.icon,
            description.enabled_by_default,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        bridge: Bridge = self.coordinator.data
        return cast(StateType, self.entity_description.value(bridge))
