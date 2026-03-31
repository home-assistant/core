"""FortiOS device tracker platform."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import FortiOSConfigEntry
from .const import DEFAULT_DEVICE_NAME, DEVICE_ICONS, FORTIOS_RESULTS_MASTER_MAC
from .coordinator import FortiOSDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FortiOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FortiOS device tracker from a config entry."""
    coordinator: FortiOSDataUpdateCoordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def update_entities() -> None:
        """Add new tracker entities from the router."""
        new_tracked = []
        devices = coordinator.data.get("devices", {})
        for mac, device in devices.items():
            if mac in tracked:
                continue
            new_tracked.append(FortiOSDeviceScanner(coordinator, device))
            tracked.add(mac)
        async_add_entities(new_tracked)

    config_entry.async_on_unload(coordinator.async_add_listener(update_entities))
    update_entities()


class FortiOSDeviceScanner(
    CoordinatorEntity[FortiOSDataUpdateCoordinator], ScannerEntity
):
    """Representation of a FortiOS connected entity."""

    _is_online: bool

    def __init__(
        self, coordinator: FortiOSDataUpdateCoordinator, device: dict[str, Any]
    ) -> None:
        """Initialize a FortiOS connected entity."""
        super().__init__(coordinator)
        mac = device.get(FORTIOS_RESULTS_MASTER_MAC, "")
        hostname = device.get("hostname")
        self._attr_name = (
            hostname or mac.strip().replace(":", "_").upper() or DEFAULT_DEVICE_NAME
        )
        self._attr_hostname = hostname
        self._attr_ip_address = device.get("ipv4_address", "")
        self._attr_mac_address = mac
        self._attr_icon = icon_for_fortios_device(device)
        self._attr_unique_id = mac
        self._is_online = device.get("is_online", False)
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the FortiOS connected entity."""
        devices = self.coordinator.data.get("devices", {})
        device = devices.get(self._attr_mac_address)
        if not device:
            return

        self._is_online = device.get("is_online", False)
        self._attr_ip_address = device.get("ipv4_address", "")
        tz = dt_util.now().tzinfo
        self._attr_extra_state_attributes = {
            "last_seen": datetime.fromtimestamp(device.get("last_seen", 0), tz),
            "os_name": device.get("os_name", ""),
            "os_version": device.get("os_version", ""),
            "ipv6_address": device.get("ipv6_address", ""),
            "hardware_vendor": device.get("hardware_vendor", ""),
            "hardware_type": device.get("hardware_type", ""),
            "hardware_version": device.get("hardware_version", ""),
            "hardware_family": device.get("hardware_family", ""),
            "is_online": device.get("is_online", ""),
        }
        super()._handle_coordinator_update()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        return True

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._attr_mac_address or ""

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._is_online


def icon_for_fortios_device(device: dict[str, Any]) -> str:
    """Return a device icon from its type."""
    return DEVICE_ICONS.get(
        str(device.get("hardware_family", "")).lower(), "mdi:help-network"
    )
