"""Support for System Bridge sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from systembridge import Bridge

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_GIGAHERTZ,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant

from . import SystemBridgeDeviceEntity
from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

ATTR_AVAILABLE = "available"
ATTR_FILESYSTEM = "filesystem"
ATTR_LOAD_AVERAGE = "load_average"
ATTR_LOAD_IDLE = "load_idle"
ATTR_LOAD_SYSTEM = "load_system"
ATTR_LOAD_USER = "load_user"
ATTR_MOUNT = "mount"
ATTR_SIZE = "size"
ATTR_TYPE = "type"
ATTR_USED = "used"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SystemBridgeCpuSpeedSensor(coordinator),
        SystemBridgeCpuTemperatureSensor(coordinator),
        SystemBridgeCpuVoltageSensor(coordinator),
        *(
            SystemBridgeFilesystemSensor(coordinator, key)
            for key, _ in coordinator.data.filesystem.fsSize.items()
        ),
        SystemBridgeMemoryFreeSensor(coordinator),
        SystemBridgeMemoryUsedSensor(coordinator),
        SystemBridgeMemoryUsedPercentageSensor(coordinator),
        SystemBridgeKernelSensor(coordinator),
        SystemBridgeOsSensor(coordinator),
        SystemBridgeProcessesLoadSensor(coordinator),
        SystemBridgeBiosVersionSensor(coordinator),
    ]

    if coordinator.data.battery.hasBattery:
        entities.append(SystemBridgeBatterySensor(coordinator))
        entities.append(SystemBridgeBatteryTimeRemainingSensor(coordinator))

    async_add_entities(entities)


class SystemBridgeSensor(SystemBridgeDeviceEntity, SensorEntity):
    """Defines a System Bridge sensor."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        key: str,
        name: str,
        icon: str | None,
        device_class: str | None,
        unit_of_measurement: str | None,
        enabled_by_default: bool,
    ) -> None:
        """Initialize System Bridge sensor."""
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement

        super().__init__(coordinator, key, name, icon, enabled_by_default)

    @property
    def device_class(self) -> str | None:
        """Return the class of this sensor."""
        return self._device_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class SystemBridgeBatterySensor(SystemBridgeSensor):
    """Defines a Battery sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "battery",
            "Battery",
            None,
            DEVICE_CLASS_BATTERY,
            PERCENTAGE,
            True,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.battery.percent


class SystemBridgeBatteryTimeRemainingSensor(SystemBridgeSensor):
    """Defines the Battery Time Remaining sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "battery_time_remaining",
            "Battery Time Remaining",
            None,
            DEVICE_CLASS_TIMESTAMP,
            None,
            True,
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        if bridge.battery.timeRemaining is None:
            return None
        return str(datetime.now() + timedelta(minutes=bridge.battery.timeRemaining))


class SystemBridgeCpuSpeedSensor(SystemBridgeSensor):
    """Defines a CPU speed sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "cpu_speed",
            "CPU Speed",
            "mdi:speedometer",
            None,
            FREQUENCY_GIGAHERTZ,
            True,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.currentSpeed.avg


class SystemBridgeCpuTemperatureSensor(SystemBridgeSensor):
    """Defines a CPU temperature sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "cpu_temperature",
            "CPU Temperature",
            None,
            DEVICE_CLASS_TEMPERATURE,
            TEMP_CELSIUS,
            False,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.temperature.main


class SystemBridgeCpuVoltageSensor(SystemBridgeSensor):
    """Defines a CPU voltage sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "cpu_voltage",
            "CPU Voltage",
            None,
            DEVICE_CLASS_VOLTAGE,
            ELECTRIC_POTENTIAL_VOLT,
            False,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.cpu.voltage


class SystemBridgeFilesystemSensor(SystemBridgeSensor):
    """Defines a filesystem sensor."""

    def __init__(
        self, coordinator: SystemBridgeDataUpdateCoordinator, key: str
    ) -> None:
        """Initialize System Bridge sensor."""
        uid_key = key.replace(":", "")
        super().__init__(
            coordinator,
            f"filesystem_{uid_key}",
            f"{key} Space Used",
            "mdi:harddisk",
            None,
            PERCENTAGE,
            True,
        )
        self._fs_key = key

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return (
            round(bridge.filesystem.fsSize[self._fs_key]["use"], 2)
            if bridge.filesystem.fsSize[self._fs_key]["use"] is not None
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        return {
            ATTR_AVAILABLE: bridge.filesystem.fsSize[self._fs_key]["available"],
            ATTR_FILESYSTEM: bridge.filesystem.fsSize[self._fs_key]["fs"],
            ATTR_MOUNT: bridge.filesystem.fsSize[self._fs_key]["mount"],
            ATTR_SIZE: bridge.filesystem.fsSize[self._fs_key]["size"],
            ATTR_TYPE: bridge.filesystem.fsSize[self._fs_key]["type"],
            ATTR_USED: bridge.filesystem.fsSize[self._fs_key]["used"],
        }


class SystemBridgeMemoryFreeSensor(SystemBridgeSensor):
    """Defines a memory free sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "memory_free",
            "Memory Free",
            "mdi:memory",
            None,
            DATA_GIGABYTES,
            True,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return (
            round(bridge.memory.free / 1000 ** 3, 2)
            if bridge.memory.free is not None
            else None
        )


class SystemBridgeMemoryUsedSensor(SystemBridgeSensor):
    """Defines a memory used sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "memory_used",
            "Memory Used",
            "mdi:memory",
            None,
            DATA_GIGABYTES,
            False,
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return (
            round(bridge.memory.used / 1000 ** 3, 2)
            if bridge.memory.used is not None
            else None
        )


class SystemBridgeMemoryUsedPercentageSensor(SystemBridgeSensor):
    """Defines a memory used percentage sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "memory_used_percentage",
            "Memory Used %",
            "mdi:memory",
            None,
            PERCENTAGE,
            True,
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return (
            round((bridge.memory.used / bridge.memory.total) * 100, 2)
            if bridge.memory.used is not None and bridge.memory.total is not None
            else None
        )


class SystemBridgeKernelSensor(SystemBridgeSensor):
    """Defines a kernel sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "kernel",
            "Kernel",
            "mdi:devices",
            None,
            None,
            True,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.os.kernel


class SystemBridgeOsSensor(SystemBridgeSensor):
    """Defines an OS sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "os",
            "Operating System",
            "mdi:devices",
            None,
            None,
            True,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return f"{bridge.os.distro} {bridge.os.release}"


class SystemBridgeProcessesLoadSensor(SystemBridgeSensor):
    """Defines a Processes Load sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "processes_load",
            "Load",
            "mdi:percent",
            None,
            PERCENTAGE,
            True,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return (
            round(bridge.processes.load.currentLoad, 2)
            if bridge.processes.load.currentLoad is not None
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        attrs = {}
        if bridge.processes.load.avgLoad is not None:
            attrs[ATTR_LOAD_AVERAGE] = round(bridge.processes.load.avgLoad, 2)
        if bridge.processes.load.currentLoadUser is not None:
            attrs[ATTR_LOAD_USER] = round(bridge.processes.load.currentLoadUser, 2)
        if bridge.processes.load.currentLoadSystem is not None:
            attrs[ATTR_LOAD_SYSTEM] = round(bridge.processes.load.currentLoadSystem, 2)
        if bridge.processes.load.currentLoadIdle is not None:
            attrs[ATTR_LOAD_IDLE] = round(bridge.processes.load.currentLoadIdle, 2)
        return attrs


class SystemBridgeBiosVersionSensor(SystemBridgeSensor):
    """Defines a bios version sensor."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            "bios_version",
            "BIOS Version",
            "mdi:chip",
            None,
            None,
            False,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.system.bios.version
