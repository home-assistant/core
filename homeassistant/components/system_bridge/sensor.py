"""Support for System Bridge sensors."""
from typing import Any, Dict, Optional

from systembridge import Bridge

from homeassistant.components.zeroconf import ATTR_HOSTNAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DOMAIN

ATTR_ARCH = "arch"
ATTR_BUILD = "build"
ATTR_CAPACITY = "capacity"
ATTR_CAPACITY_MAX = "capacity max"
ATTR_CHARGING = "charging"
ATTR_CODENAME = "codename"
ATTR_DISTRO = "distro"
ATTR_FQDN = "fqdn"
ATTR_KERNEL = "kernel"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_PLATFORM = "platform"
ATTR_RELEASE = "release"
ATTR_SERIAL = "serial"
ATTR_SERVICE_PACK = "service pack"
ATTR_TIME_REMAINING = "time remaining"
ATTR_TYPE = "type"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    async_add_entities(
        [
            BridgeBatterySensor(coordinator, bridge),
            BridgeOsSensor(coordinator, bridge),
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
        icon: str,
        device_class: str = "",
        unit_of_measurement: str = "",
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
    def unit_of_measurement(self) -> str:
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
    def state(self) -> str:
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
