"""Support for Motion Blinds using their WLAN API."""
from __future__ import annotations

from typing import TypeVar

from motionblinds import DEVICE_TYPES_GATEWAY, DEVICE_TYPES_WIFI, MotionGateway
from motionblinds.motion_blinds import MotionBlind

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DataUpdateCoordinatorMotionBlinds
from .const import (
    ATTR_AVAILABLE,
    DEFAULT_GATEWAY_NAME,
    DOMAIN,
    KEY_GATEWAY,
    MANUFACTURER,
)
from .gateway import device_name

_T = TypeVar("_T")


class MotionCoordinatorEntity(CoordinatorEntity[DataUpdateCoordinatorMotionBlinds]):
    """Representation of a Motion Blind entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinatorMotionBlinds,
        blind: MotionGateway | MotionBlind,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._blind = blind
        self._api_lock = coordinator.api_lock

        if blind.device_type in DEVICE_TYPES_GATEWAY:
            gateway = blind
        else:
            gateway = blind._gateway
        if gateway.firmware is not None:
            sw_version = f"{gateway.firmware}, protocol: {gateway.protocol}"
        else:
            sw_version = f"Protocol: {gateway.protocol}"

        if blind.device_type in DEVICE_TYPES_GATEWAY:
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, blind.mac)},
                identifiers={(DOMAIN, blind.mac)},
                manufacturer=MANUFACTURER,
                name=DEFAULT_GATEWAY_NAME,
                model="Wi-Fi bridge",
                sw_version=sw_version,
            )
        elif blind.device_type in DEVICE_TYPES_WIFI:
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, blind.mac)},
                identifiers={(DOMAIN, blind.mac)},
                manufacturer=MANUFACTURER,
                model=blind.blind_type,
                name=device_name(blind),
                sw_version=sw_version,
                hw_version=blind.wireless_name,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, blind.mac)},
                manufacturer=MANUFACTURER,
                model=blind.blind_type,
                name=device_name(blind),
                via_device=(DOMAIN, blind._gateway.mac),
                hw_version=blind.wireless_name,
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        gateway_available = self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]
        if not gateway_available or self._blind.device_type in DEVICE_TYPES_GATEWAY:
            return gateway_available

        return self.coordinator.data[self._blind.mac][ATTR_AVAILABLE]

    async def async_added_to_hass(self) -> None:
        """Subscribe to multicast pushes and register signal handler."""
        self._blind.Register_callback(self.unique_id, self.schedule_update_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        self._blind.Remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()
