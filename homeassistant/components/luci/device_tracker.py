"""Support for OpenWRT (luci) routers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LuciConfigEntry, LuciCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuciConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OpenWrt (luci) component."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add new tracker entities from the router."""
        new_entities: list[LuciScannerEntity] = []
        for mac, device in coordinator.data.items():
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(LuciScannerEntity(coordinator, mac, device))
        if new_entities:
            async_add_entities(new_entities)

    _async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))


class LuciScannerEntity(CoordinatorEntity[LuciCoordinator], ScannerEntity):
    """Representation of a device connected to an OpenWrt router."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LuciCoordinator,
        mac: str,
        device: dict[str, Any],
    ) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = mac
        self._attr_mac_address = mac
        self._attr_hostname = device.get("hostname")
        self._attr_ip_address = device.get("ip")
        self._attr_name = device.get("hostname") or mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the router."""
        return self._mac in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._mac in self.coordinator.data:
            device = self.coordinator.data[self._mac]
            self._attr_hostname = device.get("hostname")
            self._attr_ip_address = device.get("ip")
        super()._handle_coordinator_update()
