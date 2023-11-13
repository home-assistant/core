"""Base entity for the Fully Kiosk Browser integration."""
from __future__ import annotations

from yarl import URL

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator


def valid_global_mac_address(mac: str | None) -> bool:
    """Check if a MAC address is valid, non-locally administered address."""
    if not isinstance(mac, str):
        return False
    try:
        first_octet = int(mac.split(":")[0], 16)
        # If the second least-significant bit is set, it's a locally administered address, should not be used as an ID
        return not bool(first_octet & 0x2)
    except ValueError:
        return False


class FullyKioskEntity(CoordinatorEntity[FullyKioskDataUpdateCoordinator], Entity):
    """Defines a Fully Kiosk Browser entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the Fully Kiosk Browser entity."""
        super().__init__(coordinator=coordinator)

        url = URL.build(
            scheme="https" if coordinator.use_ssl else "http",
            host=coordinator.data["ip4"],
            port=2323,
        )

        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data["deviceID"])},
            name=coordinator.data["deviceName"],
            manufacturer=coordinator.data["deviceManufacturer"],
            model=coordinator.data["deviceModel"],
            sw_version=coordinator.data["appVersionName"],
            configuration_url=str(url),
        )
        if "Mac" in coordinator.data and valid_global_mac_address(
            coordinator.data["Mac"]
        ):
            device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, coordinator.data["Mac"])
            }
        self._attr_device_info = device_info
