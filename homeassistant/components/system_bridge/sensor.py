"""Support for System Bridge sensors."""
from typing import Any, Dict, Optional

from systembridge import Bridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    FREQUENCY_GIGAHERTZ,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DOMAIN

ATTR_ARCH = "arch"
ATTR_AVAILABLE = "available"
ATTR_BRAND = "brand"
ATTR_BUILD = "build"
ATTR_CAPACITY = "capacity"
ATTR_CAPACITY_MAX = "capacity_max"
ATTR_CHARGING = "charging"
ATTR_CODENAME = "codename"
ATTR_CORES = "cores"
ATTR_CORES_PHYSICAL = "cores_physical"
ATTR_DISTRO = "distro"
ATTR_FILESYSTEM = "filesystem"
ATTR_FQDN = "fqdn"
ATTR_GOVERNOR = "governor"
ATTR_HOSTNAME = "hostname"
ATTR_KERNEL = "kernel"
ATTR_LOAD_AVERAGE = "load_average"
ATTR_LOAD_IDLE = "load_idle"
ATTR_LOAD_SYSTEM = "load_system"
ATTR_LOAD_USER = "load_user"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_MOUNT = "mount"
ATTR_PLATFORM = "platform"
ATTR_RELEASE = "release"
ATTR_SERIAL = "serial"
ATTR_SERVICE_PACK = "service_pack"
ATTR_SIZE = "size"
ATTR_SPEED = "speed"
ATTR_SPEED_CURRENT_MAX = "speed_current_max"
ATTR_SPEED_CURRENT_MIN = "speed_current_min"
ATTR_SPEED_MAX = "speed_max"
ATTR_SPEED_MIN = "speed_min"
ATTR_TEMPERATURE_MAX = "temperature_max"
ATTR_TIME_REMAINING = "time_remaining"
ATTR_TYPE = "type"
ATTR_USED = "used"
ATTR_VENDOR = "vendor"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    async_add_entities(
        [
            BridgeBatterySensor(coordinator, bridge),
            BridgeCpuSpeedSensor(coordinator, bridge),
            BridgeCpuTemperatureSensor(coordinator, bridge),
            *[
                BridgeFilesystemSensor(coordinator, bridge, key)
                for key, _ in bridge.filesystem.fsSize.items()
            ],
            BridgeOsSensor(coordinator, bridge),
            BridgeProcessesLoadSensor(coordinator, bridge),
        ],
        True,
    )


class BridgeSensor(BridgeDeviceEntity):
    """Defines a System Bridge sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bridge: Bridge,
        key: str,
        name: str,
        icon: Optional[str],
        device_class: Optional[str],
        unit_of_measurement: Optional[str],
    ) -> None:
        """Initialize System Bridge sensor."""
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement

        super().__init__(coordinator, bridge, key, name, icon)

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
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
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.battery.percent

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        return {
            ATTR_CAPACITY_MAX: bridge.battery.maxCapacity,
            ATTR_CAPACITY: bridge.battery.currentCapacity,
            ATTR_CHARGING: bridge.battery.isCharging,
            ATTR_MANUFACTURER: bridge.battery.manufacturer,
            ATTR_MODEL: bridge.battery.model,
            ATTR_SERIAL: bridge.battery.serial,
            ATTR_TIME_REMAINING: bridge.battery.timeRemaining,
            ATTR_TYPE: bridge.battery.type,
            ATTR_VOLTAGE: bridge.battery.voltage,
        }


class BridgeCpuSpeedSensor(BridgeSensor):
    """Defines a CPU sensor."""

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
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.currentSpeed.avg

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        return {
            ATTR_BRAND: bridge.cpu.cpu.brand,
            ATTR_CORES_PHYSICAL: bridge.cpu.cpu.physicalCores,
            ATTR_CORES: bridge.cpu.cpu.cores,
            ATTR_GOVERNOR: bridge.cpu.cpu.governor,
            ATTR_MANUFACTURER: bridge.cpu.cpu.manufacturer,
            ATTR_SPEED_CURRENT_MAX: bridge.cpu.currentSpeed.max,
            ATTR_SPEED_CURRENT_MIN: bridge.cpu.currentSpeed.min,
            ATTR_SPEED_MAX: bridge.cpu.cpu.speedMax,
            ATTR_SPEED_MIN: bridge.cpu.cpu.speedMin,
            ATTR_SPEED: bridge.cpu.cpu.speed,
            ATTR_VENDOR: bridge.cpu.cpu.vendor,
            ATTR_VOLTAGE: bridge.cpu.cpu.voltage,
        }


class BridgeCpuTemperatureSensor(BridgeSensor):
    """Defines a CPU sensor."""

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
        )

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return bridge.cpu.temperature.main

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        return {
            ATTR_BRAND: bridge.cpu.cpu.brand,
            ATTR_CORES_PHYSICAL: bridge.cpu.cpu.physicalCores,
            ATTR_CORES: bridge.cpu.cpu.cores,
            ATTR_GOVERNOR: bridge.cpu.cpu.governor,
            ATTR_MANUFACTURER: bridge.cpu.cpu.manufacturer,
            ATTR_TEMPERATURE_MAX: bridge.cpu.temperature.max,
            ATTR_VENDOR: bridge.cpu.cpu.vendor,
            ATTR_VOLTAGE: bridge.cpu.cpu.voltage,
        }


class BridgeFilesystemSensor(BridgeSensor):
    """Defines a CPU sensor."""

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
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
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


class BridgeOsSensor(BridgeSensor):
    """Defines an OS sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(
            coordinator, bridge, "os", "Operating System", "mdi:devices", None, None
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return f"{bridge.os.distro} {bridge.os.release}"

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        bridge: Bridge = self.coordinator.data
        return {
            ATTR_ARCH: bridge.os.arch,
            ATTR_BUILD: bridge.os.build,
            ATTR_CODENAME: bridge.os.codename,
            ATTR_DISTRO: bridge.os.distro,
            ATTR_FQDN: bridge.os.fqdn,
            ATTR_HOSTNAME: bridge.os.hostname,
            ATTR_KERNEL: bridge.os.kernel,
            ATTR_PLATFORM: bridge.os.platform,
            ATTR_RELEASE: bridge.os.release,
            ATTR_SERIAL: bridge.os.serial,
            ATTR_SERVICE_PACK: bridge.os.servicepack,
        }


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
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
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
