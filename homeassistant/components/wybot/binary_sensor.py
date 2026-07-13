"""Binary sensor platform for WyBot integration."""

import logging
from typing import Any, cast, override

from wybot.dp_models import Battery, BatteryState, DockConnectionStatus, SolarStatus
from wybot.models import Group

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WyBotConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import WyBotCoordinator

_LOGGER = logging.getLogger(__name__)

# Read-only entities driven by the DataUpdateCoordinator.
PARALLEL_UPDATES = 0


def format_mac(mac: str) -> str:
    """Format a MAC address string with colons.

    Converts "CCBA97932A96" to "CC:BA:97:93:2A:96".
    """
    mac = mac.upper().replace(":", "").replace("-", "")
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WyBotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WyBot binary sensor platform."""
    coordinator = entry.runtime_data
    known_robot: set[str] = set()
    known_dock: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        """Add binary sensors for devices discovered after setup."""
        entities: list[BinarySensorEntity] = []
        for device_id in coordinator.vacuums:
            group = coordinator.data[device_id]
            if device_id not in known_robot:
                known_robot.add(device_id)
                entities.append(
                    WyBotRobotChargingBinarySensor(
                        idx=device_id, coordinator=coordinator
                    )
                )
            # The dock charging sensor describes the dock, so only create it
            # once a group actually has a dock (which may be after setup).
            if group.docker is not None and device_id not in known_dock:
                known_dock.add(device_id)
                entities.append(
                    WyBotDockChargingBinarySensor(
                        idx=device_id, coordinator=coordinator
                    )
                )
        if entities:
            async_add_entities(entities)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class WyBotBinarySensorBase(BinarySensorEntity, CoordinatorEntity[WyBotCoordinator]):
    """Base class for WyBot binary sensors."""

    _data: Group | None
    _idx: str
    _coordinator: WyBotCoordinator
    _attr_has_entity_name = True

    def __init__(self, idx: str, coordinator: WyBotCoordinator) -> None:
        """Initialize the WyBot binary sensor."""
        super().__init__(coordinator=coordinator, context=idx)
        self._idx = idx
        self._coordinator = coordinator
        self._data = coordinator.data.get(self._idx) if coordinator.data else None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if str(self._idx) in self.coordinator.data:
            self._data = self.coordinator.data[str(self._idx)]
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.available:
            return False
        if not self._data:
            return False
        if str(self._idx) not in self.coordinator.data:
            return False
        return True

    def _get_robot_name(self) -> str:
        """Get the robot device name."""
        if self._data:
            if self._data.name:
                return self._data.name
            if self._data.device and self._data.device.device_name:
                return self._data.device.device_name
            if self._data.device and self._data.device.device_type:
                return self._data.device.device_type
        return "Unknown"

    def _get_robot_model(self) -> str:
        """Get the robot device model."""
        if self._data and self._data.device:
            return self._data.device.device_type
        return "Unknown"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information for the robot."""
        connections: set[tuple[str, str]] = set()
        if self._data and self._data.device and self._data.device.ble_name:
            connections.add(
                (CONNECTION_BLUETOOTH, format_mac(self._data.device.ble_name))
            )
        # If dock exists, robot connects via dock; otherwise standalone
        via_device = None
        if self._data and self._data.docker:
            via_device = (DOMAIN, f"{self._idx}_dock")
        info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, str(self._idx))},
            "name": self._get_robot_name(),
            "manufacturer": MANUFACTURER,
            "model": self._get_robot_model(),
            "connections": connections or None,
            "via_device": via_device,
        }
        # HA's DeviceInfo TypedDict types connections/via_device as
        # non-optional, but this integration stores None to mean "unset"
        # (preserved for compatibility); cast the loosely-typed kwargs.
        return cast(DeviceInfo, info_kwargs)


class WyBotRobotChargingBinarySensor(WyBotBinarySensorBase):
    """Binary sensor for robot charging status."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_translation_key = "robot_charging"

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._idx}_robot_charging"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the robot is charging."""
        if not self._data:
            return None
        battery = self._data.get_dp(Battery)
        if battery is None:
            return None
        return battery.charge_state is BatteryState.CHARGING

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        if self._data:
            battery = self._data.get_dp(Battery)
            if battery is not None:
                attrs["charge_state"] = battery.charge_state.name
                attrs["is_fully_charged"] = battery.charge_state is BatteryState.CHARGED
        return attrs


class WyBotDockBinarySensorBase(WyBotBinarySensorBase):
    """Base class for WyBot dock binary sensors - creates a separate dock device."""

    @property
    @override
    def available(self) -> bool:
        """Dock binary sensors are unavailable when the group has no dock."""
        return (
            super().available
            and self._data is not None
            and self._data.docker is not None
        )

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information for the solar dock."""
        dock_name = "Solar Dock"
        dock_model = "Unknown"
        connections: set[tuple[str, str]] = set()
        if self._data and self._data.docker:
            dock_model = self._data.docker.docker_type
            # Use docker type as name if available
            if self._data.docker.docker_type:
                dock_name = f"{self._data.docker.docker_type} Solar Dock"
            # Add Bluetooth MAC connection if available
            if self._data.docker.ble_name:
                connections.add(
                    (CONNECTION_BLUETOOTH, format_mac(self._data.docker.ble_name))
                )
        info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, f"{self._idx}_dock")},
            "name": dock_name,
            "manufacturer": MANUFACTURER,
            "model": dock_model,
            "connections": connections or None,
        }
        # HA's DeviceInfo TypedDict types connections as non-optional, but this
        # integration stores None to mean "unset" (preserved for
        # compatibility); cast the loosely-typed kwargs.
        return cast(DeviceInfo, info_kwargs)


class WyBotDockChargingBinarySensor(WyBotDockBinarySensorBase):
    """Binary sensor for dock solar charging status."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_translation_key = "dock_charging"

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._idx}_dock_charging"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the dock is charging (solar)."""
        if not self._data:
            return None
        solar_status = self._data.get_dp(SolarStatus)
        if solar_status is None:
            return None
        return solar_status.is_charging

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        if self._data:
            # Add dock connection status
            dock_status = self._data.get_dp(DockConnectionStatus)
            if dock_status is not None:
                attrs["is_docked"] = dock_status.is_docked

            # Add solar status raw value
            solar_status = self._data.get_dp(SolarStatus)
            if solar_status is not None:
                attrs["raw_value"] = solar_status.data
        return attrs
