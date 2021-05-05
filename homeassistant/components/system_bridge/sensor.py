"""Support for System Bridge sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from systembridge import Bridge

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    FREQUENCY_GIGAHERTZ,
    PERCENTAGE,
    TEMP_CELSIUS,
    VOLT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DOMAIN

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
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    entities = [
        BridgeCpuSpeedSensor(coordinator, bridge),
        BridgeCpuTemperatureSensor(coordinator, bridge),
        BridgeCpuVoltageSensor(coordinator, bridge),
        *[
            BridgeFilesystemSensor(coordinator, bridge, key)
            for key, _ in bridge.filesystem.fsSize.items()
        ],
        BridgeKernelSensor(coordinator, bridge),
        BridgeOsSensor(coordinator, bridge),
        BridgeProcessesLoadSensor(coordinator, bridge),
    ]

    if bridge.battery.hasBattery:
        entities.append(BridgeBatterySensor(coordinator, bridge))
        entities.append(BridgeBatteryTimeRemainingSensor(coordinator, bridge))

    async_add_entities(entities)


class BridgeSensor(BridgeDeviceEntity, SensorEntity):
    """Defines a System Bridge sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bridge: Bridge,
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

        super().__init__(coordinator, bridge, key, name, icon, enabled_by_default)

    @property
    def device_class(self) -> str | None:
        """Return the class of this sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class BridgeBatterySensor(BridgeSensor):
    """Defines a Battery sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "battery",
            "Battery",
            None,
            DEVICE_CLASS_BATTERY,
            PERCENTAGE,
            True,
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.battery.percent


class BridgeBatteryTimeRemainingSensor(BridgeSensor):
    """Defines the Battery Time Remaining sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "battery_time_remaining",
            "Battery Time Remaining",
            None,
            DEVICE_CLASS_TIMESTAMP,
            None,
            True,
        )

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        if bridge.battery.timeRemaining is None:
            return None
        return str(datetime.now() + timedelta(minutes=bridge.battery.timeRemaining))


class BridgeCpuSpeedSensor(BridgeSensor):
    """Defines a CPU speed sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "cpu_speed",
            "CPU Speed",
            None,
            None,
            FREQUENCY_GIGAHERTZ,
            True,
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.currentSpeed.avg


class BridgeCpuTemperatureSensor(BridgeSensor):
    """Defines a CPU temperature sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "cpu_temperature",
            "CPU Temperature",
            None,
            DEVICE_CLASS_TEMPERATURE,
            TEMP_CELSIUS,
            False,
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.temperature.main


class BridgeCpuVoltageSensor(BridgeSensor):
    """Defines a CPU voltage sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "cpu_voltage",
            "CPU Voltage",
            None,
            DEVICE_CLASS_VOLTAGE,
            VOLT,
            False,
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.cpu.voltage


class BridgeFilesystemSensor(BridgeSensor):
    """Defines a filesystem sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge, key: str):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            f"filesystem_{key}",
            f"{key} Space Used",
            None,
            None,
            PERCENTAGE,
            True,
        )
        self._key = key

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return (
            round(bridge.filesystem.fsSize[self._key]["use"], 2)
            if bridge.filesystem.fsSize[self._key]["use"] is not None
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        return {
            ATTR_AVAILABLE: bridge.filesystem.fsSize[self._key]["available"],
            ATTR_FILESYSTEM: bridge.filesystem.fsSize[self._key]["fs"],
            ATTR_MOUNT: bridge.filesystem.fsSize[self._key]["mount"],
            ATTR_SIZE: bridge.filesystem.fsSize[self._key]["size"],
            ATTR_TYPE: bridge.filesystem.fsSize[self._key]["type"],
            ATTR_USED: bridge.filesystem.fsSize[self._key]["used"],
        }


class BridgeKernelSensor(BridgeSensor):
    """Defines a kernel sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "kernel",
            "Kernel",
            "mdi:devices",
            None,
            None,
            True,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.os.kernel


class BridgeOsSensor(BridgeSensor):
    """Defines an OS sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "os",
            "Operating System",
            "mdi:devices",
            None,
            None,
            True,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return f"{bridge.os.distro} {bridge.os.release}"


class BridgeProcessesLoadSensor(BridgeSensor):
    """Defines a Processes Load sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator,
            bridge,
            "processes_load",
            "Load",
            "mdi:percent",
            None,
            PERCENTAGE,
            True,
        )

    @property
    def state(self) -> float:
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
        return {
            ATTR_LOAD_AVERAGE: round(bridge.processes.load.avgLoad, 2)
            if bridge.processes.load.avgLoad is not None
            else None,
            ATTR_LOAD_USER: round(bridge.processes.load.currentLoadUser, 2)
            if bridge.processes.load.currentLoadUser is not None
            else None,
            ATTR_LOAD_SYSTEM: round(bridge.processes.load.currentLoadSystem, 2)
            if bridge.processes.load.currentLoadSystem is not None
            else None,
            ATTR_LOAD_IDLE: round(bridge.processes.load.currentLoadIdle, 2)
            if bridge.processes.load.currentLoadIdle is not None
            else None,
        }
